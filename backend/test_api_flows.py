"""
End-to-end API flow tests for the LMS backend.

Run with:
    python manage.py test test_api_flows
"""
import io
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from PIL import Image, ImageDraw
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Organization, User
from accounts.services import UserProvisioningError, provision_demo_user
from assessments.models import Choice, Question, Quiz, QuizAttempt
from assignments.models import Assignment
from audit.models import AuditLog
from certificates.models import Certificate, CertificateTemplate
from certificates.services import (
    MIN_AUTO_SHRINK_FONT_SIZE,
    CertificateIssuanceError,
    _fit_font,
    certificate_ineligibility_reason,
    generate_certificate,
)
from courses.models import Course, CourseAccess, DemoLessonAccess, Element, Enrollment, Lesson, Module, Slide, SlideProgress
from courses.video_streaming import build_video_stream_token
from scenarios.models import ScenarioChoice, ScenarioNode


def make_test_certificate_template(**overrides):
    """Builds a minimal, valid CertificateTemplate for tests that don't rely on the seeded platform default."""
    image_buffer = io.BytesIO()
    Image.new('RGB', (400, 300), color='white').save(image_buffer, format='PNG')
    defaults = dict(
        name='Test Template',
        background_image=SimpleUploadedFile('bg.png', image_buffer.getvalue(), content_type='image/png'),
        is_default=False,
    )
    defaults.update(overrides)
    return CertificateTemplate.objects.create(**defaults)


class BaseAPITestCase(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Acme Bank', slug='acme-bank')
        self.other_org = Organization.objects.create(name='Other Bank', slug='other-bank')

        self.learner = User.objects.create_user(
            email='learner@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org,
            first_name='Lana', last_name='Learner',
        )
        self.other_org_learner = User.objects.create_user(
            email='other-learner@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.other_org,
        )
        self.org_admin = User.objects.create_user(
            email='orgadmin@example.com', password='pass12345',
            role=User.Role.ORG_ADMIN, organization=self.org,
        )
        self.instructor = User.objects.create_user(
            email='instructor@example.com', password='pass12345',
            role=User.Role.INSTRUCTOR, organization=self.org,
        )
        self.platform_admin = User.objects.create_user(
            email='platformadmin@example.com', password='pass12345',
            role=User.Role.PLATFORM_ADMIN,
        )

        self.published_org_course = Course.objects.create(
            title='Org Onboarding', slug='org-onboarding', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        )
        self.unpublished_org_course = Course.objects.create(
            title='Org Draft', slug='org-draft', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=False,
        )
        self.platform_course = Course.objects.create(
            title='Platform Basics', slug='platform-basics',
            content_owner=Course.ContentOwner.PLATFORM, is_published=True,
        )
        self.other_org_course = Course.objects.create(
            title='Other Org Course', slug='other-org-course', organization=self.other_org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        )

        self.module = Module.objects.create(course=self.published_org_course, title='Intro', order=1)
        self.lesson1 = Lesson.objects.create(module=self.module, title='Welcome', order=1, estimated_minutes=5)
        self.lesson2 = Lesson.objects.create(module=self.module, title='Next steps', order=2, estimated_minutes=5)

        self.quiz_slide = Slide.objects.create(
            lesson=self.lesson1, order=99, title='Final Exam', slide_type=Slide.SlideType.QUIZ,
        )
        self.quiz = Quiz.objects.create(slide=self.quiz_slide, title='Final Exam', pass_percentage=50, max_attempts=2)
        self.q1 = Question.objects.create(quiz=self.quiz, question_text='2+2=?', order=1, points=1)
        self.q1_wrong = Choice.objects.create(question=self.q1, choice_text='3', is_correct=False)
        self.q1_right = Choice.objects.create(question=self.q1, choice_text='4', is_correct=True)
        self.q2 = Question.objects.create(quiz=self.quiz, question_text='Sky color?', order=2, points=1)
        self.q2_right = Choice.objects.create(question=self.q2, choice_text='Blue', is_correct=True)
        self.q2_wrong = Choice.objects.create(question=self.q2, choice_text='Green', is_correct=False)

    def auth_as(self, user):
        access = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')


class AuthFlowTests(BaseAPITestCase):
    def test_login_returns_access_and_refresh_tokens(self):
        response = self.client.post('/api/auth/login/', {'email': 'learner@example.com', 'password': 'pass12345'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_rejects_wrong_password(self):
        response = self.client.post('/api/auth/login/', {'email': 'learner@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)

    def test_refresh_returns_new_access_token(self):
        login = self.client.post('/api/auth/login/', {'email': 'learner@example.com', 'password': 'pass12345'})
        response = self.client.post('/api/auth/refresh/', {'refresh': login.data['refresh']})
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

    def test_me_returns_current_user_profile(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'learner@example.com')
        self.assertEqual(response.data['role'], 'LEARNER')
        self.assertEqual(response.data['organization']['slug'], 'acme-bank')

    def test_me_requires_authentication(self):
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, 401)


class CourseVisibilityTests(BaseAPITestCase):
    def test_learner_sees_only_published_own_org_courses_without_a_grant(self):
        self.auth_as(self.learner)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertEqual(slugs, {'org-onboarding'})

    def test_org_admin_sees_unpublished_own_org_courses_without_a_grant(self):
        self.auth_as(self.org_admin)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertEqual(slugs, {'org-onboarding', 'org-draft'})

    def test_platform_course_becomes_visible_after_grant(self):
        CourseAccess.objects.create(course=self.platform_course, organization=self.org)
        self.auth_as(self.learner)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertEqual(slugs, {'org-onboarding', 'platform-basics'})

    def test_platform_course_invisible_to_ungranted_org(self):
        CourseAccess.objects.create(course=self.platform_course, organization=self.org)
        self.auth_as(self.other_org_learner)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertNotIn('platform-basics', slugs)

    def test_platform_admin_sees_every_course(self):
        self.auth_as(self.platform_admin)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertEqual(slugs, {'org-onboarding', 'org-draft', 'platform-basics', 'other-org-course'})

    def test_learner_cannot_see_other_org_course(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/courses/other-org-course/')
        self.assertEqual(response.status_code, 404)

    def test_course_retrieve_returns_nested_modules_and_lessons(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/courses/org-onboarding/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['modules']), 1)
        self.assertEqual(response.data['modules'][0]['lessons'][0]['title'], 'Welcome')


class OrganizationAccessHardeningTests(BaseAPITestCase):
    """
    Explicit query/permission-layer coverage for cross-Organization access:
    a user authenticated as a member of one Organization must never be able
    to retrieve, list, or modify a Course (or its sub-resources) that belongs
    to a different Organization, regardless of role.
    """

    def test_learner_direct_retrieve_of_another_orgs_course_is_denied(self):
        self.auth_as(self.learner)  # self.org
        response = self.client.get(f'/api/courses/{self.other_org_course.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_learner_from_the_target_org_can_retrieve_the_same_course(self):
        self.auth_as(self.other_org_learner)  # self.other_org, matches other_org_course
        response = self.client.get(f'/api/courses/{self.other_org_course.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['slug'], self.other_org_course.slug)

    def test_other_org_learner_cannot_retrieve_this_orgs_course(self):
        self.auth_as(self.other_org_learner)
        response = self.client.get(f'/api/courses/{self.published_org_course.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_org_admin_direct_retrieve_of_another_orgs_course_is_denied(self):
        self.auth_as(self.org_admin)  # self.org
        response = self.client.get(f'/api/courses/{self.other_org_course.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_org_admin_cannot_edit_another_orgs_course(self):
        self.auth_as(self.org_admin)
        response = self.client.patch(f'/api/courses/{self.other_org_course.slug}/', {'title': 'Hacked'})
        self.assertEqual(response.status_code, 404)
        self.other_org_course.refresh_from_db()
        self.assertEqual(self.other_org_course.title, 'Other Org Course')

    def test_other_org_course_excluded_from_list_endpoint(self):
        self.auth_as(self.learner)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertNotIn(self.other_org_course.slug, slugs)

    def test_platform_admin_can_still_retrieve_any_orgs_course(self):
        self.auth_as(self.platform_admin)
        response = self.client.get(f'/api/courses/{self.other_org_course.slug}/')
        self.assertEqual(response.status_code, 200)


class CourseCatalogAndDashboardVisibilityTests(BaseAPITestCase):
    """
    Phase 32 audit: every course-listing surface in the product (the course
    catalog page, the learner/admin dashboard's "recent"/"my courses"
    widgets) is built entirely from GET /api/courses/ (CourseViewSet, scoped
    by visible_courses_for_user) plus GET /api/enrollments/ (scoped by
    RoleScopedQuerysetMixin) — there is no separate catalog/search/
    recommendation backend endpoint to audit independently. These tests
    pin that a standard (non-demo) user's course list never contains a
    course outside their own Organization's assignment, including the edge
    case of a stray Enrollment row pointing at an out-of-scope course.
    """

    def test_catalog_excludes_unpublished_other_org_and_ungranted_platform_courses(self):
        CourseAccess.objects.create(course=self.platform_course, organization=self.other_org)
        self.auth_as(self.learner)  # self.org — no grant for platform_course
        response = self.client.get('/api/courses/')
        slugs = {c['slug'] for c in response.data}
        self.assertEqual(slugs, {self.published_org_course.slug})
        self.assertNotIn(self.unpublished_org_course.slug, slugs)
        self.assertNotIn(self.other_org_course.slug, slugs)
        self.assertNotIn(self.platform_course.slug, slugs)

    def test_dashboard_course_list_never_exposes_a_course_behind_a_stray_enrollment(self):
        # Simulate a data-integrity edge case (e.g. a prior bug, a revoked
        # CourseAccess grant after enrollment) rather than one reachable
        # through the current API: an Enrollment row pointing at a course
        # outside the enrolled user's org.
        Enrollment.objects.create(user=self.other_org_learner, course=self.published_org_course)

        self.auth_as(self.other_org_learner)
        catalog = self.client.get('/api/courses/')
        self.assertNotIn(self.published_org_course.slug, {c['slug'] for c in catalog.data})

        enrollments = self.client.get('/api/enrollments/')
        self.assertEqual(enrollments.data[0]['course'], self.published_org_course.id)
        self.assertNotIn('title', enrollments.data[0])

    def test_ungranted_platform_course_absent_from_catalog_for_every_organization(self):
        for user in (self.learner, self.other_org_learner):
            self.auth_as(user)
            slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
            self.assertNotIn(self.platform_course.slug, slugs)


class EnrollmentFlowTests(BaseAPITestCase):
    def test_learner_can_enroll_and_list_own_enrollment(self):
        self.auth_as(self.learner)
        create = self.client.post('/api/enrollments/', {'course': self.published_org_course.id})
        self.assertEqual(create.status_code, 201)

        listing = self.client.get('/api/enrollments/')
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]['course'], self.published_org_course.id)

    def test_duplicate_enrollment_rejected(self):
        self.auth_as(self.learner)
        self.client.post('/api/enrollments/', {'course': self.published_org_course.id})
        response = self.client.post('/api/enrollments/', {'course': self.published_org_course.id})
        self.assertEqual(response.status_code, 400)

    def test_cannot_enroll_in_course_outside_org_access(self):
        self.auth_as(self.learner)
        response = self.client.post('/api/enrollments/', {'course': self.other_org_course.id})
        self.assertEqual(response.status_code, 400)

    def test_update_progress_to_completed_sets_completed_at(self):
        self.auth_as(self.learner)
        enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        response = self.client.patch(f'/api/enrollments/{enrollment.id}/', {'status': 'COMPLETED'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'COMPLETED')
        self.assertIsNotNone(response.data['completed_at'])
        self.assertEqual(response.data['progress_percent'], 100)

    def test_other_learner_cannot_see_or_edit_someone_elses_enrollment(self):
        enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        self.auth_as(self.other_org_learner)
        self.assertEqual(self.client.get(f'/api/enrollments/{enrollment.id}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/enrollments/{enrollment.id}/', {'progress_percent': 50}).status_code, 404)

    def test_org_admin_sees_enrollments_within_their_org_only(self):
        Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        Enrollment.objects.create(user=self.other_org_learner, course=self.other_org_course)
        self.auth_as(self.org_admin)
        response = self.client.get('/api/enrollments/')
        self.assertEqual({row['user'] for row in response.data}, {self.learner.id})

    def test_platform_admin_sees_all_enrollments(self):
        Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        Enrollment.objects.create(user=self.other_org_learner, course=self.other_org_course)
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/enrollments/')
        self.assertEqual(len(response.data), 2)

    def test_list_enrollments_filtered_by_course_query_param(self):
        Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        Enrollment.objects.create(user=self.learner, course=self.platform_course)
        self.auth_as(self.learner)
        response = self.client.get(f'/api/enrollments/?course={self.published_org_course.id}')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['course'], self.published_org_course.id)

    def test_complete_lesson_updates_progress_and_completed_ids(self):
        self.auth_as(self.learner)
        enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)

        response = self.client.post(
            f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson1.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['completed_lesson_ids'], [self.lesson1.id])
        self.assertEqual(response.data['progress_percent'], 50)
        self.assertEqual(response.data['status'], 'IN_PROGRESS')

    def test_completing_all_lessons_marks_enrollment_completed(self):
        self.auth_as(self.learner)
        enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)

        self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson1.id})
        response = self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson2.id})

        self.assertEqual(response.data['progress_percent'], 100)
        self.assertEqual(response.data['status'], 'COMPLETED')
        self.assertIsNotNone(response.data['completed_at'])
        self.assertCountEqual(response.data['completed_lesson_ids'], [self.lesson1.id, self.lesson2.id])

    def test_complete_lesson_is_idempotent(self):
        self.auth_as(self.learner)
        enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson1.id})
        response = self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson1.id})
        self.assertEqual(response.data['completed_lesson_ids'], [self.lesson1.id])
        self.assertEqual(response.data['progress_percent'], 50)

    def test_cannot_complete_lesson_from_a_different_course(self):
        self.auth_as(self.learner)
        enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        other_module = Module.objects.create(course=self.platform_course, title='Other', order=1)
        other_lesson = Lesson.objects.create(module=other_module, title='Other lesson', order=1)
        response = self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': other_lesson.id})
        self.assertEqual(response.status_code, 404)

    def test_other_learner_cannot_complete_lesson_on_someone_elses_enrollment(self):
        enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        self.auth_as(self.other_org_learner)
        response = self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson1.id})
        self.assertEqual(response.status_code, 404)


class QuizFlowTests(BaseAPITestCase):
    def test_learner_cannot_see_correct_answers(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/quizzes/{self.quiz.id}/')
        self.assertEqual(response.status_code, 200)
        for question in response.data['questions']:
            for choice in question['choices']:
                self.assertNotIn('is_correct', choice)

    def test_org_admin_can_see_correct_answers(self):
        self.auth_as(self.org_admin)
        response = self.client.get(f'/api/quizzes/{self.quiz.id}/')
        for question in response.data['questions']:
            for choice in question['choices']:
                self.assertIn('is_correct', choice)

    def test_submit_scores_attempt_and_marks_passed(self):
        self.auth_as(self.learner)
        payload = {
            'answers': [
                {'question': self.q1.id, 'selected_choices': [self.q1_right.id]},
                {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
            ],
        }
        response = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['score_percent'], '100.00')
        self.assertTrue(response.data['passed'])

    def test_submit_with_one_wrong_answer_scores_partial(self):
        self.auth_as(self.learner)
        payload = {
            'answers': [
                {'question': self.q1.id, 'selected_choices': [self.q1_wrong.id]},
                {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
            ],
        }
        response = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        self.assertEqual(response.data['score_percent'], '50.00')
        self.assertTrue(response.data['passed'])  # pass_percentage is 50

    def test_max_attempts_enforced(self):
        self.auth_as(self.learner)
        payload = {
            'answers': [
                {'question': self.q1.id, 'selected_choices': [self.q1_right.id]},
                {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
            ],
        }
        self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        third = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        self.assertEqual(third.status_code, 400)
        self.assertEqual(QuizAttempt.objects.filter(user=self.learner, quiz=self.quiz).count(), 2)

    def test_submit_rejects_choice_from_a_different_question(self):
        self.auth_as(self.learner)
        payload = {
            'answers': [
                {'question': self.q1.id, 'selected_choices': [self.q2_right.id]},
                {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
            ],
        }
        response = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        self.assertEqual(response.status_code, 400)


class MultipleAnswerScoringTests(BaseAPITestCase):
    """MULTIPLE_ANSWER questions score all-or-nothing: every correct option
    selected, no incorrect ones — see assessments.views.QuizViewSet.submit."""

    def setUp(self):
        super().setUp()
        self.ma_question = Question.objects.create(
            quiz=self.quiz,
            question_text='Which are primary colors?',
            question_type=Question.QuestionType.MULTIPLE_ANSWER,
            order=3,
            points=1,
            explanation='Red, blue, and yellow are the primary colors.',
            feedback_correct='Nice — you got every primary color.',
            feedback_incorrect='Not quite — check which ones are true primaries.',
        )
        self.red = Choice.objects.create(question=self.ma_question, choice_text='Red', is_correct=True)
        self.blue = Choice.objects.create(question=self.ma_question, choice_text='Blue', is_correct=True)
        self.green = Choice.objects.create(question=self.ma_question, choice_text='Green', is_correct=False)
        self.purple = Choice.objects.create(question=self.ma_question, choice_text='Purple', is_correct=False)

    def _submit(self, selected_choice_ids):
        self.auth_as(self.learner)
        payload = {
            'answers': [
                {'question': self.q1.id, 'selected_choices': [self.q1_right.id]},
                {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
                {'question': self.ma_question.id, 'selected_choices': selected_choice_ids},
            ],
        }
        return self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')

    def _ma_answer(self, response):
        return next(a for a in response.data['answers'] if a['question'] == self.ma_question.id)

    def test_selecting_both_correct_options_scores_correct(self):
        response = self._submit([self.red.id, self.blue.id])
        self.assertEqual(response.status_code, 201)
        answer = self._ma_answer(response)
        self.assertTrue(answer['is_correct'])

    def test_selecting_only_one_correct_option_scores_incorrect(self):
        response = self._submit([self.red.id])
        answer = self._ma_answer(response)
        self.assertFalse(answer['is_correct'])

    def test_selecting_a_correct_option_plus_a_distractor_scores_incorrect(self):
        response = self._submit([self.red.id, self.green.id])
        answer = self._ma_answer(response)
        self.assertFalse(answer['is_correct'])

    def test_single_choice_scoring_is_unaffected(self):
        # Same payload shape/logic path as MULTIPLE_ANSWER (exact set
        # equality) — confirms the existing SINGLE_CHOICE behavior wasn't
        # changed by adding MULTIPLE_ANSWER support.
        response = self._submit([self.red.id, self.blue.id])
        q1_answer = next(a for a in response.data['answers'] if a['question'] == self.q1.id)
        self.assertTrue(q1_answer['is_correct'])

    def test_result_reveals_correct_choice_ids_explanation_and_feedback(self):
        response = self._submit([self.red.id, self.blue.id])
        answer = self._ma_answer(response)
        self.assertEqual(set(answer['correct_choice_ids']), {self.red.id, self.blue.id})
        self.assertEqual(answer['explanation'], 'Red, blue, and yellow are the primary colors.')
        self.assertEqual(answer['feedback_correct'], 'Nice — you got every primary color.')
        self.assertEqual(answer['feedback_incorrect'], 'Not quite — check which ones are true primaries.')

    def test_quiz_detail_still_hides_answer_key_from_learner_before_submitting(self):
        # The reveal lives on the QuizAttempt/QuizAnswer response only — the
        # quiz-taking endpoint itself must still strip the answer key.
        self.auth_as(self.learner)
        response = self.client.get(f'/api/quizzes/{self.quiz.id}/')
        ma_data = next(q for q in response.data['questions'] if q['id'] == self.ma_question.id)
        self.assertNotIn('explanation', ma_data)
        self.assertNotIn('feedback_correct', ma_data)
        for choice in ma_data['choices']:
            self.assertNotIn('is_correct', choice)


class ChoiceDisplayOrderTests(BaseAPITestCase):
    """
    Phase 35: SINGLE_CHOICE/MULTIPLE_CHOICE/MULTIPLE_ANSWER/TRUE_FALSE choices
    must not always render in their stored creation order for a learner —
    that lets the correct answer's position (not its content) become a
    learnable pattern. See QuestionSerializer.to_representation.
    """

    def setUp(self):
        super().setUp()
        self.sc_question = Question.objects.create(
            quiz=self.quiz,
            question_text='Which is the capital of France?',
            question_type=Question.QuestionType.SINGLE_CHOICE,
            order=4,
            points=1,
        )
        # The correct choice is deliberately created first — the exact
        # authoring pattern that produced the positional-bias bug, so a
        # regression here would show every fetch's choices[0] as correct.
        self.paris = Choice.objects.create(question=self.sc_question, choice_text='Paris', is_correct=True, order=1)
        self.berlin = Choice.objects.create(question=self.sc_question, choice_text='Berlin', is_correct=False, order=2)
        self.madrid = Choice.objects.create(question=self.sc_question, choice_text='Madrid', is_correct=False, order=3)
        self.rome = Choice.objects.create(question=self.sc_question, choice_text='Rome', is_correct=False, order=4)
        self.lisbon = Choice.objects.create(question=self.sc_question, choice_text='Lisbon', is_correct=False, order=5)
        self.oslo = Choice.objects.create(question=self.sc_question, choice_text='Oslo', is_correct=False, order=6)

    def _fetch_choice_order(self):
        response = self.client.get(f'/api/quizzes/{self.quiz.id}/')
        sc_data = next(q for q in response.data['questions'] if q['id'] == self.sc_question.id)
        return [choice['id'] for choice in sc_data['choices']]

    def test_learner_sees_shuffled_choice_order_across_fetches(self):
        self.auth_as(self.learner)
        orders = [tuple(self._fetch_choice_order()) for _ in range(30)]
        creation_order = (self.paris.id, self.berlin.id, self.madrid.id, self.rome.id, self.lisbon.id, self.oslo.id)

        # Every fetch still contains exactly the same 6 choices...
        for order in orders:
            self.assertEqual(set(order), set(creation_order))
        # ...but with 6 choices shuffled independently 30 times, seeing the
        # exact same order every single time is astronomically unlikely
        # (~1/720 per trial) unless shuffling isn't actually happening.
        self.assertGreater(len(set(orders)), 1)

    def test_correct_choices_position_varies_not_always_first(self):
        self.auth_as(self.learner)
        positions = [self._fetch_choice_order().index(self.paris.id) for _ in range(30)]
        # If the bug were present, every position would be 0 (creation order,
        # correct choice authored first).
        self.assertGreater(len(set(positions)), 1)

    def test_privileged_role_sees_stable_authored_order(self):
        # Instructors/admins are editing, not guessing — shuffling would just
        # make the authoring UI's own choices jump around, so it stays off
        # for privileged roles, same as every other question type here.
        self.auth_as(self.instructor)
        orders = [tuple(self._fetch_choice_order()) for _ in range(5)]
        creation_order = (self.paris.id, self.berlin.id, self.madrid.id, self.rome.id, self.lisbon.id, self.oslo.id)
        self.assertEqual(set(orders), {creation_order})

    def test_grading_is_unaffected_by_display_shuffle(self):
        # Grading is by Choice id set-equality (assessments.views.QuizViewSet
        # .submit), never by the shuffled array position, so this must keep
        # passing regardless of how many times the quiz was re-fetched first.
        self.auth_as(self.learner)
        for _ in range(10):
            self._fetch_choice_order()

        payload = {
            'answers': [
                {'question': self.q1.id, 'selected_choices': [self.q1_right.id]},
                {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
                {'question': self.sc_question.id, 'selected_choices': [self.paris.id]},
            ],
        }
        response = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        sc_answer = next(a for a in response.data['answers'] if a['question'] == self.sc_question.id)
        self.assertTrue(sc_answer['is_correct'])

        wrong_payload = {
            'answers': [
                {'question': self.q1.id, 'selected_choices': [self.q1_right.id]},
                {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
                {'question': self.sc_question.id, 'selected_choices': [self.berlin.id]},
            ],
        }
        wrong_response = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', wrong_payload, format='json')
        wrong_answer = next(a for a in wrong_response.data['answers'] if a['question'] == self.sc_question.id)
        self.assertFalse(wrong_answer['is_correct'])


class CertificateFlowTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED,
        )
        attempt = QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)
        self.certificate = generate_certificate(self.learner, self.published_org_course)
        self.attempt = attempt

    def test_learner_can_list_and_retrieve_own_certificate(self):
        self.auth_as(self.learner)
        listing = self.client.get('/api/certificates/')
        self.assertEqual(len(listing.data), 1)

        retrieve = self.client.get(f'/api/certificates/{self.certificate.id}/')
        self.assertEqual(retrieve.status_code, 200)
        self.assertEqual(retrieve.data['certificate_number'], self.certificate.certificate_number)

    def test_other_learner_cannot_see_certificate(self):
        self.auth_as(self.other_org_learner)
        response = self.client.get(f'/api/certificates/{self.certificate.id}/')
        self.assertEqual(response.status_code, 404)

    def test_download_returns_pdf(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/certificates/{self.certificate.id}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_public_verify_endpoint_returns_certificate_details_without_auth(self):
        self.client.credentials()  # no auth header
        response = self.client.get(f'/verify/{self.certificate.verification_token}/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['valid'])
        self.assertEqual(response.json()['learner_name'], 'Lana Learner')

    def test_public_verify_endpoint_returns_404_for_unknown_token(self):
        self.client.credentials()
        response = self.client.get('/verify/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['valid'])


class CertificateIssueEndpointTests(BaseAPITestCase):
    def test_issue_endpoint_creates_certificate_once_eligible(self):
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED,
        )
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)

        self.auth_as(self.learner)
        response = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn('certificate_number', response.data)
        self.assertTrue(response.data['pdf_file'])

    def test_issue_endpoint_rejects_when_quiz_not_attempted(self):
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED,
        )
        self.auth_as(self.learner)
        response = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('has not been attempted yet', response.data['detail'])

    def test_issue_endpoint_is_idempotent(self):
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED,
        )
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)

        self.auth_as(self.learner)
        first = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        second = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        self.assertEqual(first.data['id'], second.data['id'])

    def test_issue_endpoint_rejects_course_outside_requesters_organization(self):
        # Directly construct an eligible-looking Enrollment/QuizAttempt for a
        # learner in a different org than the course, bypassing the normal
        # enroll-time visible_courses_for_user gate, to prove the issue
        # endpoint itself also org-scopes the course lookup as defense in depth.
        Enrollment.objects.create(
            user=self.other_org_learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED,
        )
        QuizAttempt.objects.create(
            user=self.other_org_learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100
        )

        self.auth_as(self.other_org_learner)
        response = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        self.assertEqual(response.status_code, 404)


class CourseAverageCertificateEligibilityTests(BaseAPITestCase):
    """
    Phase 34: certificate eligibility is governed by the course-wide AVERAGE
    score across all of the course's quizzes (each quiz's own best attempt),
    not a requirement that every individual quiz independently score above
    its own Quiz.pass_percentage. self.quiz (pass_percentage=50) already
    exists on lesson1 from BaseAPITestCase; a second quiz (pass_percentage=
    70) is added on lesson2 here so the average can diverge from any single
    quiz's individual pass/fail outcome. published_org_course.
    certificate_pass_threshold is the default (70).
    """

    def setUp(self):
        super().setUp()
        self.quiz2_slide = Slide.objects.create(
            lesson=self.lesson2, order=99, title='Second Exam', slide_type=Slide.SlideType.QUIZ,
        )
        self.quiz2 = Quiz.objects.create(slide=self.quiz2_slide, title='Second Exam', pass_percentage=70)
        self.enrollment = Enrollment.objects.create(
            user=self.learner, course=self.published_org_course, status=Enrollment.Status.COMPLETED,
        )

    def test_certificate_issues_when_average_meets_threshold_despite_one_quiz_individually_failed(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=False, score_percent=40)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=True, score_percent=100)
        # Average = (40 + 100) / 2 = 70, meets the 70% threshold — even though
        # self.quiz was individually failed against its own pass_percentage=50.

        self.assertIsNone(certificate_ineligibility_reason(self.learner, self.published_org_course))

        self.auth_as(self.learner)
        response = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Certificate.objects.filter(user=self.learner, course=self.published_org_course).exists())

    def test_certificate_denied_when_average_below_threshold_despite_one_quiz_individually_passed(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=False, score_percent=20)
        # Average = (100 + 20) / 2 = 60, below the 70% threshold — even though
        # self.quiz was individually passed against its own pass_percentage=50.

        reason = certificate_ineligibility_reason(self.learner, self.published_org_course)
        self.assertIsNotNone(reason)
        self.assertIn('60.0%', reason)

        self.auth_as(self.learner)
        response = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Certificate.objects.filter(user=self.learner, course=self.published_org_course).exists())

    def test_unattempted_quiz_blocks_issuance_even_with_a_high_score_elsewhere(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)
        # self.quiz2 was never attempted at all.

        reason = certificate_ineligibility_reason(self.learner, self.published_org_course)
        self.assertIsNotNone(reason)
        self.assertIn('has not been attempted yet', reason)

    def test_enrollment_serializer_exposes_ineligible_reason_only_once_completed_and_short(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=False, score_percent=20)

        self.auth_as(self.learner)
        response = self.client.get(f'/api/enrollments/{self.enrollment.id}/')
        self.assertIsNotNone(response.data['certificate_ineligible_reason'])
        self.assertIn('60.0%', response.data['certificate_ineligible_reason'])

    def test_enrollment_serializer_reason_is_null_when_average_meets_threshold(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=False, score_percent=40)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=True, score_percent=100)

        self.auth_as(self.learner)
        response = self.client.get(f'/api/enrollments/{self.enrollment.id}/')
        self.assertIsNone(response.data['certificate_ineligible_reason'])

    def test_enrollment_serializer_reason_is_null_while_still_in_progress(self):
        self.enrollment.status = Enrollment.Status.IN_PROGRESS
        self.enrollment.save()

        self.auth_as(self.learner)
        response = self.client.get(f'/api/enrollments/{self.enrollment.id}/')
        self.assertIsNone(response.data['certificate_ineligible_reason'])


class OrganizationListTests(BaseAPITestCase):
    def test_platform_admin_can_list_organizations(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/organizations/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.org.slug, [o['slug'] for o in response.data])

    def test_learner_forbidden_from_organization_list(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/organizations/')
        self.assertEqual(response.status_code, 403)


class CourseBuilderTests(BaseAPITestCase):
    def test_learner_cannot_create_course(self):
        self.auth_as(self.learner)
        response = self.client.post('/api/courses/', {'title': 'New', 'slug': 'new-course'})
        self.assertEqual(response.status_code, 403)

    def test_instructor_create_forces_own_organization_and_content_owner(self):
        self.auth_as(self.instructor)
        response = self.client.post('/api/courses/', {
            'title': 'Instructor Course', 'slug': 'instructor-course',
            'organization': self.other_org.id, 'content_owner': 'PLATFORM',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['organization'], self.org.id)
        self.assertEqual(response.data['content_owner'], 'ORGANIZATION')
        self.assertEqual(Course.objects.get(slug='instructor-course').created_by, self.instructor)

    def test_platform_admin_create_forces_platform_content_owner(self):
        self.auth_as(self.platform_admin)
        response = self.client.post('/api/courses/', {
            'title': 'Platform Managed', 'slug': 'platform-managed',
            'organization': self.other_org.id, 'content_owner': 'ORGANIZATION',
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['organization'], self.other_org.id)
        self.assertEqual(response.data['content_owner'], 'PLATFORM')

    def test_org_admin_cannot_edit_content_owner_on_update(self):
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/courses/{self.published_org_course.slug}/', {'content_owner': 'PLATFORM'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['content_owner'], 'ORGANIZATION')

    def test_instructor_cannot_edit_other_org_course(self):
        self.auth_as(self.instructor)
        response = self.client.patch(f'/api/courses/{self.other_org_course.slug}/', {'title': 'Hacked'})
        self.assertEqual(response.status_code, 404)

    def test_org_admin_can_edit_draft_course_in_own_org(self):
        self.auth_as(self.org_admin)
        response = self.client.patch(f'/api/courses/{self.unpublished_org_course.slug}/', {'is_published': True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_published'])

    def test_org_admin_cannot_move_course_to_another_org(self):
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/courses/{self.published_org_course.slug}/', {'organization': self.other_org.id}
        )
        self.assertEqual(response.status_code, 200)
        self.published_org_course.refresh_from_db()
        self.assertEqual(self.published_org_course.organization_id, self.org.id)


class CourseAccessGrantTests(BaseAPITestCase):
    def test_platform_admin_can_grant_and_list_access(self):
        self.auth_as(self.platform_admin)
        grant_response = self.client.post(
            f'/api/courses/{self.platform_course.slug}/access-grants/', {'organization': self.org.id}
        )
        self.assertEqual(grant_response.status_code, 201)

        list_response = self.client.get(f'/api/courses/{self.platform_course.slug}/access-grants/')
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['organization']['id'], self.org.id)

    def test_granting_is_idempotent(self):
        self.auth_as(self.platform_admin)
        first = self.client.post(f'/api/courses/{self.platform_course.slug}/access-grants/', {'organization': self.org.id})
        second = self.client.post(f'/api/courses/{self.platform_course.slug}/access-grants/', {'organization': self.org.id})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(CourseAccess.objects.filter(course=self.platform_course, organization=self.org).count(), 1)

    def test_cannot_grant_access_to_an_organization_owned_course(self):
        self.auth_as(self.platform_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/access-grants/', {'organization': self.other_org.id}
        )
        self.assertEqual(response.status_code, 400)

    def test_revoke_removes_the_grant(self):
        CourseAccess.objects.create(course=self.platform_course, organization=self.org)
        self.auth_as(self.platform_admin)
        response = self.client.delete(
            f'/api/courses/{self.platform_course.slug}/access-grants/revoke/', {'organization': self.org.id},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(CourseAccess.objects.filter(course=self.platform_course, organization=self.org).exists())

    def test_org_admin_cannot_manage_grants_on_platform_course(self):
        self.auth_as(self.org_admin)
        response = self.client.post(
            f'/api/courses/{self.platform_course.slug}/access-grants/', {'organization': self.org.id}
        )
        # editable_courses_for_user excludes PLATFORM-owned courses for ORG_ADMIN,
        # so the object lookup itself 404s before any content_owner check runs.
        self.assertEqual(response.status_code, 404)

    def test_org_admin_with_granted_access_still_cannot_edit_platform_course(self):
        CourseAccess.objects.create(course=self.platform_course, organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(f'/api/courses/{self.platform_course.slug}/', {'title': 'Hacked'})
        self.assertEqual(response.status_code, 404)


class VideoStreamingTests(BaseAPITestCase):
    """
    Phase 36: an uploaded video Element is served through a short-lived,
    per-user signed streaming URL (courses.video_streaming) rather than its
    raw, permanently-public storage URL.
    """

    def setUp(self):
        super().setUp()
        self.video_slide = Slide.objects.create(
            lesson=self.lesson1, order=98, title='Intro Video', slide_type=Slide.SlideType.CONTENT,
        )
        self.video_content = b'fake-video-bytes-0123456789'
        self.video_element = Element.objects.create(
            slide=self.video_slide,
            order=1,
            element_type=Element.ElementType.VIDEO_AUDIO,
            video_file=SimpleUploadedFile('lesson.mp4', self.video_content, content_type='video/mp4'),
        )

    def _stream_url(self, element, user):
        token = build_video_stream_token(user.id, element.id)
        return f'/api/elements/{element.id}/video/?token={token}'

    def test_element_serializer_returns_streaming_url_not_raw_file_url(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/elements/?slide={self.video_slide.id}')
        video_file_url = response.data[0]['video_file']
        self.assertIn(f'/api/elements/{self.video_element.id}/video/', video_file_url)
        self.assertIn('token=', video_file_url)
        self.assertNotIn('/media/element_videos/', video_file_url)

    def test_stream_endpoint_serves_full_video_with_valid_token(self):
        response = self.client.get(self._stream_url(self.video_element, self.learner))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'video/mp4')
        self.assertEqual(b''.join(response.streaming_content), self.video_content)

    def test_stream_endpoint_supports_byte_range_requests(self):
        response = self.client.get(self._stream_url(self.video_element, self.learner), HTTP_RANGE='bytes=5-9')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Range'], f'bytes 5-9/{len(self.video_content)}')
        self.assertEqual(b''.join(response.streaming_content), self.video_content[5:10])

    def test_stream_endpoint_rejects_missing_or_garbage_token(self):
        no_token = self.client.get(f'/api/elements/{self.video_element.id}/video/')
        self.assertEqual(no_token.status_code, 403)

        bad_token = self.client.get(f'/api/elements/{self.video_element.id}/video/?token=garbage')
        self.assertEqual(bad_token.status_code, 403)

    def test_stream_endpoint_rejects_token_minted_for_a_different_element(self):
        other_element = Element.objects.create(
            slide=self.video_slide, order=2, element_type=Element.ElementType.TEXT, rich_text='<p>x</p>',
        )
        token = build_video_stream_token(self.learner.id, other_element.id)
        response = self.client.get(f'/api/elements/{self.video_element.id}/video/?token={token}')
        self.assertEqual(response.status_code, 403)

    def test_stream_endpoint_rejects_user_outside_course_organization(self):
        response = self.client.get(self._stream_url(self.video_element, self.other_org_learner))
        self.assertEqual(response.status_code, 404)

    def test_stream_endpoint_respects_demo_lesson_lock(self):
        demo_learner = User.objects.create_user(
            email='demo-video@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org, is_demo=True,
        )
        self.published_org_course.is_demo_available = True
        self.published_org_course.save()
        # lesson1 (the video's lesson) is intentionally left without a
        # DemoLessonAccess grant, so it stays locked for this demo user.

        response = self.client.get(self._stream_url(self.video_element, demo_learner))
        self.assertEqual(response.status_code, 403)

        DemoLessonAccess.objects.create(course=self.published_org_course, lesson=self.lesson1)
        granted_response = self.client.get(self._stream_url(self.video_element, demo_learner))
        self.assertEqual(granted_response.status_code, 200)


class ModuleLessonBuilderTests(BaseAPITestCase):
    def test_org_admin_can_create_module_and_lesson(self):
        self.auth_as(self.org_admin)
        module_response = self.client.post('/api/modules/', {
            'course': self.published_org_course.id, 'title': 'New Module', 'order': 5,
        })
        self.assertEqual(module_response.status_code, 201)

        lesson_response = self.client.post('/api/lessons/', {
            'module': module_response.data['id'], 'title': 'New Lesson',
            'lesson_type': 'TEXT', 'order': 1,
        })
        self.assertEqual(lesson_response.status_code, 201)

    def test_instructor_cannot_create_module_for_other_org_course(self):
        self.auth_as(self.instructor)
        response = self.client.post('/api/modules/', {
            'course': self.other_org_course.id, 'title': 'Nope', 'order': 1,
        })
        self.assertEqual(response.status_code, 400)

    def test_lesson_file_extension_validated_through_api(self):
        self.auth_as(self.org_admin)
        bad_file = SimpleUploadedFile('lesson.exe', b'not a video', content_type='application/octet-stream')
        response = self.client.post('/api/lessons/', {
            'module': self.module.id, 'title': 'Bad Video', 'lesson_type': 'VIDEO',
            'order': 9, 'content_file': bad_file,
        }, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_learner_cannot_create_lesson(self):
        self.auth_as(self.learner)
        response = self.client.post('/api/lessons/', {
            'module': self.module.id, 'title': 'Nope', 'lesson_type': 'TEXT', 'order': 9,
        })
        self.assertEqual(response.status_code, 403)


class QuizBuilderTests(BaseAPITestCase):
    def test_org_admin_can_build_quiz_question_choice(self):
        self.auth_as(self.org_admin)
        new_quiz_slide = Slide.objects.create(
            lesson=self.lesson2, order=99, title='New Quiz', slide_type=Slide.SlideType.QUIZ,
        )
        quiz_response = self.client.post('/api/quizzes/', {
            'slide': new_quiz_slide.id, 'title': 'New Quiz', 'pass_percentage': 60,
        })
        self.assertEqual(quiz_response.status_code, 201)

        question_response = self.client.post('/api/questions/', {
            'quiz': quiz_response.data['id'], 'question_text': 'Q1?',
            'question_type': 'SINGLE_CHOICE', 'order': 1, 'points': 1,
        })
        self.assertEqual(question_response.status_code, 201)

        choice_response = self.client.post('/api/choices/', {
            'question': question_response.data['id'], 'choice_text': 'A', 'is_correct': True,
        })
        self.assertEqual(choice_response.status_code, 201)

    def test_learner_cannot_create_quiz(self):
        self.auth_as(self.learner)
        new_quiz_slide = Slide.objects.create(
            lesson=self.lesson2, order=99, title='Nope', slide_type=Slide.SlideType.QUIZ,
        )
        response = self.client.post('/api/quizzes/', {
            'slide': new_quiz_slide.id, 'title': 'Nope',
        })
        self.assertEqual(response.status_code, 403)

    def test_cannot_add_question_to_other_org_quiz(self):
        other_module = Module.objects.create(course=self.other_org_course, title='Other', order=1)
        other_lesson = Lesson.objects.create(module=other_module, title='Other lesson', order=1)
        other_quiz_slide = Slide.objects.create(
            lesson=other_lesson, order=1, title='Other Quiz', slide_type=Slide.SlideType.QUIZ,
        )
        other_quiz = Quiz.objects.create(slide=other_quiz_slide, title='Other Quiz')
        self.auth_as(self.instructor)
        response = self.client.post('/api/questions/', {
            'quiz': other_quiz.id, 'question_text': 'Q?', 'order': 1, 'points': 1,
        })
        self.assertEqual(response.status_code, 400)


class BulkEnrollTests(BaseAPITestCase):
    def test_bulk_enroll_csv_enrolls_existing_users(self):
        csv_content = f'email\n{self.learner.email}\nnobody@example.com\n'.encode()
        upload = SimpleUploadedFile('emails.csv', csv_content, content_type='text/csv')

        self.auth_as(self.org_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/bulk-enroll/', {'file': upload}, format='multipart'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['enrolled'], [self.learner.email])
        self.assertEqual(response.data['not_found'], ['nobody@example.com'])
        self.assertTrue(Enrollment.objects.filter(user=self.learner, course=self.published_org_course).exists())

    def test_bulk_enroll_already_enrolled_is_reported_separately(self):
        Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        csv_content = f'{self.learner.email}\n'.encode()
        upload = SimpleUploadedFile('emails.csv', csv_content, content_type='text/csv')

        self.auth_as(self.org_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/bulk-enroll/', {'file': upload}, format='multipart'
        )
        self.assertEqual(response.data['already_enrolled'], [self.learner.email])
        self.assertEqual(response.data['enrolled'], [])

    def test_bulk_enroll_forbidden_for_learner(self):
        upload = SimpleUploadedFile('emails.csv', b'a@example.com\n', content_type='text/csv')
        self.auth_as(self.learner)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/bulk-enroll/', {'file': upload}, format='multipart'
        )
        self.assertEqual(response.status_code, 403)

    def test_bulk_enroll_rejects_course_outside_org(self):
        upload = SimpleUploadedFile('emails.csv', f'{self.learner.email}\n'.encode(), content_type='text/csv')
        self.auth_as(self.instructor)
        response = self.client.post(
            f'/api/courses/{self.other_org_course.slug}/bulk-enroll/', {'file': upload}, format='multipart'
        )
        self.assertEqual(response.status_code, 404)

    def test_bulk_enroll_rejects_user_from_a_different_organization(self):
        csv_content = f'{self.other_org_learner.email}\n'.encode()
        upload = SimpleUploadedFile('emails.csv', csv_content, content_type='text/csv')

        self.auth_as(self.org_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/bulk-enroll/', {'file': upload}, format='multipart'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['wrong_organization'], [self.other_org_learner.email])
        self.assertEqual(response.data['enrolled'], [])
        self.assertFalse(
            Enrollment.objects.filter(user=self.other_org_learner, course=self.published_org_course).exists()
        )

    def test_bulk_enroll_platform_admin_may_enroll_any_org_into_a_platform_course(self):
        csv_content = f'{self.other_org_learner.email}\n'.encode()
        upload = SimpleUploadedFile('emails.csv', csv_content, content_type='text/csv')

        self.auth_as(self.platform_admin)
        response = self.client.post(
            f'/api/courses/{self.platform_course.slug}/bulk-enroll/', {'file': upload}, format='multipart'
        )
        self.assertEqual(response.data['enrolled'], [self.other_org_learner.email])
        self.assertTrue(Enrollment.objects.filter(user=self.other_org_learner, course=self.platform_course).exists())


class InviteLearnerTests(BaseAPITestCase):
    def test_invite_enrolls_existing_user_in_own_org(self):
        self.auth_as(self.org_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/invite/', {'email': self.learner.email}
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Enrollment.objects.filter(user=self.learner, course=self.published_org_course).exists())

    def test_invite_rejects_user_from_a_different_organization(self):
        self.auth_as(self.org_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/invite/', {'email': self.other_org_learner.email}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            Enrollment.objects.filter(user=self.other_org_learner, course=self.published_org_course).exists()
        )

    def test_invite_unknown_email_returns_404(self):
        self.auth_as(self.org_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/invite/', {'email': 'nobody@example.com'}
        )
        self.assertEqual(response.status_code, 404)

    def test_invite_rejects_course_outside_org(self):
        self.auth_as(self.instructor)
        response = self.client.post(
            f'/api/courses/{self.other_org_course.slug}/invite/', {'email': self.learner.email}
        )
        self.assertEqual(response.status_code, 404)


class EnrollmentReportTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.enrollment = Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED,
        )
        QuizAttempt.objects.create(
            user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=90,
        )
        Enrollment.objects.create(user=self.other_org_learner, course=self.other_org_course)

    def test_learner_forbidden_from_report(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/reports/enrollments/')
        self.assertEqual(response.status_code, 403)

    def test_org_admin_sees_only_their_org_rows(self):
        self.auth_as(self.org_admin)
        response = self.client.get('/api/reports/enrollments/')
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row['learner_email'], self.learner.email)
        self.assertEqual(row['status'], 'COMPLETED')
        self.assertEqual(row['score_percent'], 90.0)

    def test_platform_admin_sees_all_rows(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/enrollments/')
        self.assertEqual(len(response.data), 2)

    def test_report_filterable_by_status(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/enrollments/?status=NOT_STARTED')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['learner_email'], self.other_org_learner.email)

    def test_report_csv_export(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/enrollments/?export=csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode()
        self.assertIn(self.learner.email, content)
        self.assertIn('90.0', content)

    def test_report_csv_export_neutralizes_formula_injection(self):
        evil_learner = User.objects.create_user(
            email='formula@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org,
            first_name='=HYPERLINK("http://evil.test")', last_name='X',
        )
        Enrollment.objects.create(user=evil_learner, course=self.published_org_course)

        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/enrollments/?export=csv')
        content = response.content.decode()
        self.assertNotIn('\n=HYPERLINK', content)
        self.assertIn("'=HYPERLINK", content)


class AdminAnalyticsTests(BaseAPITestCase):
    """Phase 37: admin analytics dashboard grouped by Organization."""

    def setUp(self):
        super().setUp()
        # Second quiz on lesson2 so final_score can diverge from any single
        # quiz's own pass/fail, same fixture shape as
        # CourseAverageCertificateEligibilityTests.
        self.quiz2_slide = Slide.objects.create(
            lesson=self.lesson2, order=99, title='Second Exam', slide_type=Slide.SlideType.QUIZ,
        )
        self.quiz2 = Quiz.objects.create(slide=self.quiz2_slide, title='Second Exam', pass_percentage=70)

        self.enrollment = Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED, progress_percent=100,
        )
        SlideProgress.objects.create(
            enrollment=self.enrollment, slide=self.quiz_slide, time_spent_seconds=300, completed_at=timezone.now(),
        )
        SlideProgress.objects.create(
            enrollment=self.enrollment, slide=self.quiz2_slide, time_spent_seconds=120, completed_at=timezone.now(),
        )
        # quiz1: failed then retaken and passed; quiz2: passed on the first try.
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=False, score_percent=40)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=2, passed=True, score_percent=90)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=True, score_percent=100)
        # Average of best scores = (90 + 100) / 2 = 95, clears the 70% default threshold.

        self.other_org_enrollment = Enrollment.objects.create(
            user=self.other_org_learner, course=self.other_org_course, status=Enrollment.Status.IN_PROGRESS,
            progress_percent=40,
        )

    def _row_for(self, response, user_email):
        for org_group in response.data:
            for row in org_group['rows']:
                if row['user_email'] == user_email:
                    return row
        return None

    def test_learner_forbidden(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/reports/analytics/')
        self.assertEqual(response.status_code, 403)

    def test_org_admin_sees_only_their_own_organization_grouped(self):
        self.auth_as(self.org_admin)
        response = self.client.get('/api/reports/analytics/')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['organization_name'], 'Acme Bank')
        self.assertEqual(len(response.data[0]['rows']), 1)

    def test_org_admin_organization_filter_param_is_ignored(self):
        self.auth_as(self.org_admin)
        response = self.client.get(f'/api/reports/analytics/?organization={self.other_org.id}')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['organization_name'], 'Acme Bank')

    def test_platform_admin_sees_every_organization_grouped(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/analytics/')
        org_names = {group['organization_name'] for group in response.data}
        self.assertEqual(org_names, {'Acme Bank', 'Other Bank'})

    def test_platform_admin_can_filter_by_organization(self):
        self.auth_as(self.platform_admin)
        response = self.client.get(f'/api/reports/analytics/?organization={self.other_org.id}')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['organization_name'], 'Other Bank')

    def test_course_filter_narrows_rows(self):
        self.auth_as(self.platform_admin)
        response = self.client.get(f'/api/reports/analytics/?course={self.other_org_course.id}')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['rows'][0]['user_email'], self.other_org_learner.email)

    def test_row_reports_completion_pass_status_time_spent_and_final_score(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/analytics/')
        row = self._row_for(response, self.learner.email)
        self.assertEqual(row['progress_percent'], 100)
        self.assertEqual(row['pass_status'], 'PASSED')
        self.assertEqual(row['final_score'], 95.0)
        self.assertEqual(row['time_spent_seconds'], 420)
        self.assertEqual(row['total_quiz_attempts'], 3)

    def test_row_includes_per_quiz_retake_attempts_and_scores(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/analytics/')
        row = self._row_for(response, self.learner.email)
        quiz1 = next(q for q in row['quizzes'] if q['quiz_id'] == self.quiz.id)
        self.assertEqual(quiz1['attempt_count'], 2)
        self.assertEqual([a['score_percent'] for a in quiz1['attempts']], [40.0, 90.0])
        self.assertEqual(quiz1['best_score'], 90.0)

    def test_incomplete_enrollment_reports_status_not_a_pass_fail_verdict(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/analytics/')
        row = self._row_for(response, self.other_org_learner.email)
        self.assertEqual(row['pass_status'], 'IN_PROGRESS')
        self.assertIsNone(row['final_score'])

    def test_average_below_threshold_reports_failed_despite_individual_pass(self):
        self.other_org_learner.organization = self.org
        self.other_org_learner.save()
        failing_module = Module.objects.create(course=self.unpublished_org_course, title='Only Module', order=1)
        failing_lesson = Lesson.objects.create(module=failing_module, title='Only Lesson', order=1, estimated_minutes=5)
        failing_quiz_slide = Slide.objects.create(
            lesson=failing_lesson, order=1, title='Only Exam', slide_type=Slide.SlideType.QUIZ,
        )
        failing_quiz = Quiz.objects.create(slide=failing_quiz_slide, title='Only Exam', pass_percentage=50)
        QuizAttempt.objects.create(
            user=self.other_org_learner, quiz=failing_quiz, attempt_number=1, passed=True, score_percent=60,
        )
        Enrollment.objects.create(
            user=self.other_org_learner, course=self.unpublished_org_course,
            status=Enrollment.Status.COMPLETED, progress_percent=100,
        )

        self.auth_as(self.platform_admin)
        response = self.client.get(f'/api/reports/analytics/?course={self.unpublished_org_course.id}')
        row = self._row_for(response, self.other_org_learner.email)
        self.assertEqual(row['pass_status'], 'FAILED')
        self.assertEqual(row['final_score'], 60.0)

    def test_xlsx_export_matches_on_screen_data(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/analytics/?export=xlsx')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        workbook = load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        header_row = [cell.value for cell in sheet[1]]
        self.assertEqual(
            header_row,
            [
                'Organization', 'User Name', 'User Email', 'Course', 'Status',
                '% Completion', 'Pass/Fail', 'Final Score', 'Time Spent',
                'Total Quiz Attempts', 'Attempt Details',
            ],
        )

        data_rows = list(sheet.iter_rows(min_row=2, values_only=True))
        learner_row = next(r for r in data_rows if r[2] == self.learner.email)
        self.assertEqual(learner_row[0], 'Acme Bank')
        self.assertEqual(learner_row[4], 'COMPLETED')
        self.assertEqual(learner_row[5], 1.0)  # 100% stored as a fraction for the '0%' number format
        self.assertEqual(learner_row[6], 'PASSED')
        self.assertEqual(learner_row[7], 95.0)
        self.assertEqual(learner_row[8], '7m')
        self.assertEqual(learner_row[9], 3)
        self.assertIn('Final Exam', learner_row[10])
        self.assertIn('Second Exam', learner_row[10])

    def test_xlsx_export_neutralizes_formula_injection(self):
        evil_learner = User.objects.create_user(
            email='evil-analytics@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org,
            first_name='=HYPERLINK("http://evil.test")', last_name='X',
        )
        Enrollment.objects.create(user=evil_learner, course=self.published_org_course)

        self.auth_as(self.platform_admin)
        response = self.client.get('/api/reports/analytics/?export=xlsx')
        workbook = load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        names = [row[1] for row in sheet.iter_rows(min_row=2, values_only=True)]
        self.assertIn("'=HYPERLINK(\"http://evil.test\") X", names)


class RateLimitingTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_login_is_rate_limited(self):
        payload = {'email': self.learner.email, 'password': 'wrong-password'}
        statuses = [self.client.post('/api/auth/login/', payload).status_code for _ in range(10)]
        self.assertTrue(all(code == 401 for code in statuses))

        throttled = self.client.post('/api/auth/login/', payload)
        self.assertEqual(throttled.status_code, 429)

    def test_quiz_submit_is_rate_limited(self):
        self.auth_as(self.learner)
        payload = {'answers': [
            {'question': self.q1.id, 'selected_choices': [self.q1_right.id]},
            {'question': self.q2.id, 'selected_choices': [self.q2_right.id]},
        ]}
        # max_attempts=2 on self.quiz would mask the throttle after 2 tries, so
        # raise it for this test to isolate the rate limit specifically.
        self.quiz.max_attempts = None
        self.quiz.save()

        statuses = [
            self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json').status_code
            for _ in range(20)
        ]
        self.assertTrue(all(code == 201 for code in statuses))

        throttled = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', payload, format='json')
        self.assertEqual(throttled.status_code, 429)


class AuditLogTests(BaseAPITestCase):
    def test_login_is_audit_logged(self):
        self.client.post('/api/auth/login/', {'email': self.learner.email, 'password': 'pass12345'})
        log = AuditLog.objects.get(action=AuditLog.Action.LOGIN, object_id=str(self.learner.id))
        self.assertEqual(log.user, self.learner)

    def test_failed_login_is_not_audit_logged(self):
        self.client.post('/api/auth/login/', {'email': self.learner.email, 'password': 'wrong'})
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.LOGIN).exists())

    def test_course_creation_is_audit_logged(self):
        self.auth_as(self.platform_admin)
        response = self.client.post('/api/courses/', {'title': 'Audited Course', 'slug': 'audited-course'})
        log = AuditLog.objects.get(action=AuditLog.Action.COURSE_CREATED, object_id=str(response.data['id']))
        self.assertEqual(log.user, self.platform_admin)

    def test_enrollment_create_and_update_are_audit_logged(self):
        self.auth_as(self.learner)
        create_response = self.client.post('/api/enrollments/', {'course': self.published_org_course.id})
        enrollment_id = create_response.data['id']
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.ENROLLMENT_CREATED, object_id=str(enrollment_id)).exists()
        )

        self.client.patch(f'/api/enrollments/{enrollment_id}/', {'status': 'IN_PROGRESS'})
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.ENROLLMENT_UPDATED, object_id=str(enrollment_id)).exists()
        )

    def test_certificate_generation_is_audit_logged(self):
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course, status=Enrollment.Status.COMPLETED,
        )
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)
        certificate = generate_certificate(self.learner, self.published_org_course)

        log = AuditLog.objects.get(action=AuditLog.Action.CERTIFICATE_GENERATED, object_id=str(certificate.id))
        self.assertEqual(log.user, self.learner)


class CertificateTemplateRenderingTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course, status=Enrollment.Status.COMPLETED,
        )
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)

    def test_generate_certificate_renders_a_valid_pdf_against_seeded_default_template(self):
        certificate = generate_certificate(self.learner, self.published_org_course)
        pdf_bytes = certificate.pdf_file.read()
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_generate_certificate_raises_when_no_template_is_configured(self):
        CertificateTemplate.objects.all().delete()
        with self.assertRaises(CertificateIssuanceError):
            generate_certificate(self.learner, self.published_org_course)

    def test_course_specific_template_overrides_platform_default(self):
        course_template = make_test_certificate_template(name='Course-specific template')
        self.published_org_course.certificate_template = course_template
        self.published_org_course.save()

        certificate = generate_certificate(self.learner, self.published_org_course)
        pdf_bytes = certificate.pdf_file.read()
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_saving_a_new_default_template_unsets_the_previous_one(self):
        original_default = CertificateTemplate.objects.get(is_default=True)
        new_default = make_test_certificate_template(name='New default', is_default=True)

        original_default.refresh_from_db()
        self.assertFalse(original_default.is_default)
        self.assertTrue(new_default.is_default)
        self.assertEqual(CertificateTemplate.objects.filter(is_default=True).count(), 1)

    def test_long_name_and_course_title_render_without_error(self):
        self.learner.first_name = 'Alexandria' * 5
        self.learner.last_name = 'Featherington-Papadopoulos' * 3
        self.learner.save()
        self.published_org_course.title = 'Advanced Regulatory Compliance and Risk Management ' * 4
        self.published_org_course.save()

        certificate = generate_certificate(self.learner, self.published_org_course)
        pdf_bytes = certificate.pdf_file.read()
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))


class FontAutoShrinkTests(TestCase):
    """Unit-level coverage of the name/course-title overflow guard in certificates.services._fit_font."""

    def setUp(self):
        self.image = Image.new('RGB', (2000, 1414), color='white')
        self.draw = ImageDraw.Draw(self.image)
        self.max_width_px = 2000 * 0.84

    def test_short_text_keeps_the_requested_font_size(self):
        font = _fit_font(None, 60, 'Jane Doe', self.draw, self.max_width_px)
        self.assertEqual(font.size, 60)

    def test_long_text_shrinks_down_to_the_minimum_font_size(self):
        # A max width this narrow can never be satisfied, so the loop should bottom out at the floor.
        font = _fit_font(None, 110, 'A very long staff name that will not fit', self.draw, max_width_px=50)
        self.assertEqual(font.size, MIN_AUTO_SHRINK_FONT_SIZE)

    def test_moderately_long_text_shrinks_below_the_initial_size(self):
        font = _fit_font(None, 110, 'A very long staff name that will not fit ' * 3, self.draw, self.max_width_px)
        self.assertLess(font.size, 110)

    def test_shrunk_text_fits_within_the_max_width(self):
        text = 'A Notably Long Course Title That Should Trigger Auto-Shrink Handling'
        font = _fit_font(None, 110, text, self.draw, self.max_width_px)
        left, _top, right, _bottom = self.draw.textbbox((0, 0), text, font=font)
        self.assertTrue((right - left) <= self.max_width_px or font.size == MIN_AUTO_SHRINK_FONT_SIZE)


class CertificateTemplateViewSetTests(BaseAPITestCase):
    def test_learner_cannot_list_certificate_templates(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/certificate-templates/')
        self.assertEqual(response.status_code, 403)

    def test_instructor_can_list_certificate_templates(self):
        self.auth_as(self.instructor)
        response = self.client.get('/api/certificate-templates/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

    def test_instructor_can_update_calibration_fields(self):
        template = CertificateTemplate.objects.get(is_default=True)
        self.auth_as(self.instructor)
        response = self.client.patch(
            f'/api/certificate-templates/{template.id}/',
            {'staff_name_x_percent': 42.5, 'staff_name_text_align': 'LEFT'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        template.refresh_from_db()
        self.assertEqual(template.staff_name_x_percent, 42.5)
        self.assertEqual(template.staff_name_text_align, 'LEFT')

    def test_unauthenticated_request_is_rejected(self):
        self.client.credentials()
        response = self.client.get('/api/certificate-templates/')
        self.assertEqual(response.status_code, 401)


class DemoUserProvisioningServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Acme Bank', slug='acme-bank-demo')

    def test_creates_demo_learner_with_must_reset_password_and_sends_invite(self):
        user = provision_demo_user(name='Dana Demo', email='dana@example.com', organization=self.org)

        self.assertEqual(user.role, User.Role.LEARNER)
        self.assertTrue(user.is_demo)
        self.assertTrue(user.must_reset_password)
        self.assertEqual(user.first_name, 'Dana')
        self.assertEqual(user.last_name, 'Demo')
        self.assertEqual(user.organization, self.org)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)
        self.assertIn('temporary password', mail.outbox[0].body.lower())

    def test_duplicate_email_is_rejected_case_insensitively(self):
        provision_demo_user(name='Dana Demo', email='dana@example.com', organization=self.org)
        with self.assertRaises(UserProvisioningError):
            provision_demo_user(name='Dana Two', email='DANA@example.com', organization=self.org)

    def test_missing_name_is_rejected(self):
        with self.assertRaises(UserProvisioningError):
            provision_demo_user(name='  ', email='dana@example.com', organization=self.org)

    def test_email_send_failure_rolls_back_the_account(self):
        with patch('accounts.services.EmailMultiAlternatives.send', side_effect=Exception('smtp down')):
            with self.assertRaises(UserProvisioningError):
                provision_demo_user(name='Dana Demo', email='dana@example.com', organization=self.org)

        # The whole operation is atomic — a failed invite must not leave a
        # stranded account with a password nobody received.
        self.assertFalse(User.objects.filter(email='dana@example.com').exists())


class DemoUserApiTests(BaseAPITestCase):
    def test_learner_cannot_create_demo_user(self):
        self.auth_as(self.learner)
        response = self.client.post(
            '/api/demo-users/', {'name': 'Dana Demo', 'email': 'dana@example.com', 'organization': self.org.id}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_can_create_demo_user(self):
        self.auth_as(self.instructor)
        response = self.client.post(
            '/api/demo-users/', {'name': 'Dana Demo', 'email': 'dana@example.com', 'organization': self.org.id}
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            User.objects.filter(email='dana@example.com', is_demo=True, must_reset_password=True).exists()
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_duplicate_email_returns_400_not_500(self):
        self.auth_as(self.instructor)
        response = self.client.post(
            '/api/demo-users/', {'name': 'Dana Demo', 'email': self.learner.email, 'organization': self.org.id}
        )
        self.assertEqual(response.status_code, 400)

    def test_bulk_upload_reports_per_row_success_and_failure(self):
        csv_content = (
            'name,email,organization\n'
            f'Alice Alpha,alice@example.com,{self.org.name}\n'
            f'Bob Beta,bob@example.com,{self.org.name}\n'
            f'Bob Duplicate,bob@example.com,{self.org.name}\n'
            'Missing Org,noorg@example.com,Nonexistent Org\n'
            'OnlyTwoColumns,twocols@example.com\n'
        )
        upload = SimpleUploadedFile('demo_users.csv', csv_content.encode('utf-8'), content_type='text/csv')

        self.auth_as(self.instructor)
        response = self.client.post('/api/demo-users/bulk/', {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], ['alice@example.com', 'bob@example.com'])

        failures_by_email = {f['email']: f['reason'] for f in response.data['failed']}
        self.assertIn('Duplicate email', failures_by_email['bob@example.com'])
        self.assertIn('not found', failures_by_email['noorg@example.com'])
        self.assertIn('Malformed row', failures_by_email['twocols@example.com'])
        self.assertEqual(len(mail.outbox), 2)

    def test_bulk_upload_captures_designation_and_phone_number(self):
        csv_content = (
            'name,email,organization,designation,phone_number\n'
            f'Alice Alpha,alice@example.com,{self.org.name},Compliance Officer,+977-1-4123456\n'
        )
        upload = SimpleUploadedFile('demo_users.csv', csv_content.encode('utf-8'), content_type='text/csv')

        self.auth_as(self.instructor)
        response = self.client.post('/api/demo-users/bulk/', {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], ['alice@example.com'])

        user = User.objects.get(email='alice@example.com')
        self.assertEqual(user.designation, 'Compliance Officer')
        self.assertEqual(user.phone_number, '+977-1-4123456')

    def test_bulk_upload_reports_existing_user_as_failure_not_500(self):
        csv_content = f'name,email,organization\nExisting User,{self.learner.email},{self.org.name}\n'
        upload = SimpleUploadedFile('demo_users.csv', csv_content.encode('utf-8'), content_type='text/csv')

        self.auth_as(self.instructor)
        response = self.client.post('/api/demo-users/bulk/', {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], [])
        self.assertEqual(len(response.data['failed']), 1)
        self.assertIn('already exists', response.data['failed'][0]['reason'])

    def test_bulk_upload_requires_a_file(self):
        self.auth_as(self.instructor)
        response = self.client.post('/api/demo-users/bulk/', {}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_learner_cannot_bulk_upload(self):
        upload = SimpleUploadedFile('demo_users.csv', b'name,email,organization\n', content_type='text/csv')
        self.auth_as(self.learner)
        response = self.client.post('/api/demo-users/bulk/', {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 403)


class OrgAdminApiTests(BaseAPITestCase):
    def test_platform_admin_can_create_org_admin(self):
        self.auth_as(self.platform_admin)
        response = self.client.post(
            '/api/org-admins/', {'name': 'Jane Manager', 'email': 'jane@example.com', 'organization': self.org.id}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'ORG_ADMIN')
        self.assertFalse(response.data['is_demo'])
        self.assertTrue(response.data['must_reset_password'])

        user = User.objects.get(email='jane@example.com')
        self.assertEqual(user.role, User.Role.ORG_ADMIN)
        self.assertFalse(user.is_demo)
        self.assertEqual(user.organization, self.org)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('administrator', mail.outbox[0].subject.lower())

    def test_org_admin_cannot_create_org_admin(self):
        self.auth_as(self.org_admin)
        response = self.client.post(
            '/api/org-admins/', {'name': 'Jane Manager', 'email': 'jane@example.com', 'organization': self.org.id}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_instructor_cannot_create_org_admin(self):
        self.auth_as(self.instructor)
        response = self.client.post(
            '/api/org-admins/', {'name': 'Jane Manager', 'email': 'jane@example.com', 'organization': self.org.id}
        )
        self.assertEqual(response.status_code, 403)

    def test_duplicate_email_returns_400_not_500(self):
        self.auth_as(self.platform_admin)
        response = self.client.post(
            '/api/org-admins/', {'name': 'Dup', 'email': self.learner.email, 'organization': self.org.id}
        )
        self.assertEqual(response.status_code, 400)


class SetPasswordApiTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.temp_password = 'Temp-Pass-9x7Q'
        self.demo_user = User.objects.create_user(
            email='dana@example.com', password=self.temp_password,
            role=User.Role.LEARNER, organization=self.org,
            first_name='Dana', last_name='Demo',
            is_demo=True, must_reset_password=True,
        )

    def test_new_password_clears_must_reset_flag(self):
        # No current_password field — reaching this endpoint already required
        # a valid access token, which the caller could only have obtained by
        # authenticating with the temp password moments earlier.
        self.auth_as(self.demo_user)
        response = self.client.post('/api/auth/set-password/', {
            'new_password': 'BrandNewPassw0rd1',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['must_reset_password'])

        self.demo_user.refresh_from_db()
        self.assertFalse(self.demo_user.must_reset_password)
        self.assertTrue(self.demo_user.check_password('BrandNewPassw0rd1'))

    def test_too_short_new_password_is_rejected_by_validators(self):
        self.auth_as(self.demo_user)
        response = self.client.post('/api/auth/set-password/', {'new_password': 'ab1'})
        self.assertEqual(response.status_code, 400)

        self.demo_user.refresh_from_db()
        self.assertTrue(self.demo_user.must_reset_password)

    def test_new_password_missing_a_digit_is_rejected(self):
        self.auth_as(self.demo_user)
        response = self.client.post('/api/auth/set-password/', {'new_password': 'allletters'})
        self.assertEqual(response.status_code, 400)

        self.demo_user.refresh_from_db()
        self.assertTrue(self.demo_user.must_reset_password)

    def test_new_password_missing_a_letter_is_rejected(self):
        self.auth_as(self.demo_user)
        # Also all-numeric, so this doubles as coverage for NumericPasswordValidator.
        response = self.client.post('/api/auth/set-password/', {'new_password': '12345678'})
        self.assertEqual(response.status_code, 400)

        self.demo_user.refresh_from_db()
        self.assertTrue(self.demo_user.must_reset_password)

    def test_me_endpoint_reflects_must_reset_password(self):
        self.auth_as(self.demo_user)
        response = self.client.get('/api/auth/me/')
        self.assertTrue(response.data['must_reset_password'])
        self.assertTrue(response.data['is_demo'])


class DemoUserCatalogVisibilityTests(BaseAPITestCase):
    """
    Phase 33: demo users see the FULL course catalog (every published course,
    regardless of Organization), with courses outside their own org's normal
    assignment flagged is_locked=True rather than hidden. Locked courses stay
    a teaser card only — retrieval and enrollment are still denied
    server-side, matching visible_courses_for_user exactly.
    """

    def setUp(self):
        super().setUp()
        self.demo_learner = User.objects.create_user(
            email='demo-catalog@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org,
            is_demo=True,
        )

    def _by_slug(self, response):
        return {c['slug']: c for c in response.data}

    def test_demo_user_sees_every_published_course_across_organizations(self):
        self.auth_as(self.demo_learner)
        response = self.client.get('/api/courses/')
        slugs = self._by_slug(response)
        self.assertIn(self.published_org_course.slug, slugs)
        self.assertIn(self.other_org_course.slug, slugs)
        self.assertIn(self.platform_course.slug, slugs)
        # Drafts are still withheld entirely — is_published gates content
        # readiness, not the demo teaser mechanism.
        self.assertNotIn(self.unpublished_org_course.slug, slugs)

    def test_own_org_course_is_unlocked_others_are_locked(self):
        self.auth_as(self.demo_learner)
        courses = self._by_slug(self.client.get('/api/courses/'))
        self.assertFalse(courses[self.published_org_course.slug]['is_locked'])
        self.assertTrue(courses[self.other_org_course.slug]['is_locked'])
        self.assertTrue(courses[self.platform_course.slug]['is_locked'])

    def test_unlocked_courses_sort_before_locked_ones(self):
        # platform_course and other_org_course are both locked for this demo
        # user and created after published_org_course (Course.Meta.ordering
        # is -created_at) — without the lock-status sort, they'd outrank the
        # one unlocked course. Assert the unlocked/locked split wins first.
        self.auth_as(self.demo_learner)
        response = self.client.get('/api/courses/')
        lock_flags = [row['is_locked'] for row in response.data]
        self.assertEqual(lock_flags, sorted(lock_flags))
        self.assertFalse(response.data[0]['is_locked'])
        self.assertEqual(response.data[0]['slug'], self.published_org_course.slug)

    def test_granted_platform_course_becomes_unlocked_for_demo_user(self):
        CourseAccess.objects.create(course=self.platform_course, organization=self.org)
        self.auth_as(self.demo_learner)
        courses = self._by_slug(self.client.get('/api/courses/'))
        self.assertFalse(courses[self.platform_course.slug]['is_locked'])

    def test_non_demo_learner_never_sees_is_locked_true(self):
        self.auth_as(self.learner)
        courses = self._by_slug(self.client.get('/api/courses/'))
        self.assertEqual(set(courses), {self.published_org_course.slug})
        self.assertFalse(courses[self.published_org_course.slug]['is_locked'])

    def test_force_navigating_to_a_locked_course_url_is_denied(self):
        self.auth_as(self.demo_learner)
        response = self.client.get(f'/api/courses/{self.other_org_course.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_demo_user_cannot_enroll_in_a_locked_course(self):
        self.auth_as(self.demo_learner)
        response = self.client.post('/api/enrollments/', {'course': self.other_org_course.id})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            Enrollment.objects.filter(user=self.demo_learner, course=self.other_org_course).exists()
        )

    def test_demo_user_can_retrieve_and_enroll_in_an_assigned_course(self):
        self.auth_as(self.demo_learner)
        retrieve = self.client.get(f'/api/courses/{self.published_org_course.slug}/')
        self.assertEqual(retrieve.status_code, 200)

        enroll = self.client.post('/api/enrollments/', {'course': self.published_org_course.id})
        self.assertEqual(enroll.status_code, 201)


class DemoLessonAccessTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.demo_learner = User.objects.create_user(
            email='demo@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org,
            is_demo=True,
        )
        Enrollment.objects.create(
            user=self.demo_learner, course=self.published_org_course, status=Enrollment.Status.IN_PROGRESS
        )
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course, status=Enrollment.Status.IN_PROGRESS
        )

        self.published_org_course.is_demo_available = True
        self.published_org_course.save()
        # lesson1 is granted; lesson2 is intentionally left locked.
        DemoLessonAccess.objects.create(course=self.published_org_course, lesson=self.lesson1)

    # --- Course detail tree ---

    def _lessons_by_id(self, response):
        return {lesson['id']: lesson for module in response.data['modules'] for lesson in module['lessons']}

    def test_demo_user_sees_locked_lesson_with_no_slides(self):
        self.auth_as(self.demo_learner)
        response = self.client.get(f'/api/courses/{self.published_org_course.slug}/')
        lessons = self._lessons_by_id(response)
        self.assertFalse(lessons[self.lesson1.id]['is_locked'])
        self.assertTrue(lessons[self.lesson2.id]['is_locked'])
        self.assertEqual(lessons[self.lesson2.id]['slides'], [])

    def test_non_demo_user_sees_every_lesson_unlocked(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/courses/{self.published_org_course.slug}/')
        lessons = self._lessons_by_id(response)
        self.assertFalse(lessons[self.lesson1.id]['is_locked'])
        self.assertFalse(lessons[self.lesson2.id]['is_locked'])
        self.assertGreater(len(lessons[self.lesson1.id]['slides']), 0)

    def test_demo_user_unaffected_when_course_is_not_demo_available(self):
        self.published_org_course.is_demo_available = False
        self.published_org_course.save()
        self.auth_as(self.demo_learner)
        response = self.client.get(f'/api/courses/{self.published_org_course.slug}/')
        lessons = self._lessons_by_id(response)
        self.assertFalse(lessons[self.lesson2.id]['is_locked'])

    # --- Enrollment progress-writing endpoints ---

    def test_demo_user_cannot_complete_locked_lesson(self):
        enrollment = Enrollment.objects.get(user=self.demo_learner, course=self.published_org_course)
        self.auth_as(self.demo_learner)
        response = self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson2.id})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(enrollment.lesson_progress.filter(lesson=self.lesson2).exists())

    def test_demo_user_can_complete_granted_lesson(self):
        enrollment = Enrollment.objects.get(user=self.demo_learner, course=self.published_org_course)
        self.auth_as(self.demo_learner)
        response = self.client.post(f'/api/enrollments/{enrollment.id}/complete-lesson/', {'lesson': self.lesson1.id})
        self.assertEqual(response.status_code, 200)

    def test_demo_user_cannot_write_slide_progress_on_locked_lesson(self):
        locked_slide = Slide.objects.create(lesson=self.lesson2, order=1, slide_type=Slide.SlideType.CONTENT)
        enrollment = Enrollment.objects.get(user=self.demo_learner, course=self.published_org_course)
        self.auth_as(self.demo_learner)
        response = self.client.post(
            f'/api/enrollments/{enrollment.id}/slide-progress/', {'slide': locked_slide.id, 'completed': True}
        )
        self.assertEqual(response.status_code, 400)

    def test_non_demo_user_can_write_slide_progress_on_any_lesson(self):
        open_slide = Slide.objects.create(lesson=self.lesson2, order=1, slide_type=Slide.SlideType.CONTENT)
        enrollment = Enrollment.objects.get(user=self.learner, course=self.published_org_course)
        self.auth_as(self.learner)
        response = self.client.post(
            f'/api/enrollments/{enrollment.id}/slide-progress/', {'slide': open_slide.id, 'completed': True}
        )
        self.assertEqual(response.status_code, 200)

    # --- CONTENT (Element) read path ---

    def test_demo_user_cannot_fetch_elements_of_locked_lesson(self):
        locked_slide = Slide.objects.create(lesson=self.lesson2, order=1, slide_type=Slide.SlideType.CONTENT)
        Element.objects.create(slide=locked_slide, order=1, element_type=Element.ElementType.TEXT, rich_text='secret')
        self.auth_as(self.demo_learner)
        response = self.client.get(f'/api/elements/?slide={locked_slide.id}')
        self.assertEqual(response.data, [])

    def test_demo_user_can_fetch_elements_of_granted_lesson(self):
        granted_slide = Slide.objects.create(lesson=self.lesson1, order=2, slide_type=Slide.SlideType.CONTENT)
        Element.objects.create(slide=granted_slide, order=1, element_type=Element.ElementType.TEXT, rich_text='hello')
        self.auth_as(self.demo_learner)
        response = self.client.get(f'/api/elements/?slide={granted_slide.id}')
        self.assertEqual(len(response.data), 1)

    # --- QUIZ read path ---

    def test_demo_user_cannot_fetch_quiz_of_locked_lesson(self):
        locked_slide = Slide.objects.create(lesson=self.lesson2, order=2, slide_type=Slide.SlideType.QUIZ)
        locked_quiz = Quiz.objects.create(slide=locked_slide, title='Locked quiz', pass_percentage=50)
        self.auth_as(self.demo_learner)
        response = self.client.get(f'/api/quizzes/{locked_quiz.id}/')
        self.assertEqual(response.status_code, 404)

    def test_demo_user_can_fetch_quiz_of_granted_lesson(self):
        # self.quiz's slide (self.quiz_slide) is on lesson1, which is granted.
        self.auth_as(self.demo_learner)
        response = self.client.get(f'/api/quizzes/{self.quiz.id}/')
        self.assertEqual(response.status_code, 200)

    # --- ASSIGNMENT submission write path ---

    def test_demo_user_cannot_submit_assignment_on_locked_lesson(self):
        locked_slide = Slide.objects.create(lesson=self.lesson2, order=3, slide_type=Slide.SlideType.ASSIGNMENT)
        assignment = Assignment.objects.create(slide=locked_slide, instructions='Do the thing')
        self.auth_as(self.demo_learner)
        response = self.client.post(
            '/api/assignment-submissions/', {'assignment': assignment.id, 'text_response': 'my answer'}
        )
        self.assertEqual(response.status_code, 400)

    # --- SCENARIO attempt write path ---

    def test_demo_user_cannot_submit_scenario_attempt_on_locked_lesson(self):
        locked_slide = Slide.objects.create(lesson=self.lesson2, order=4, slide_type=Slide.SlideType.SCENARIO)
        start_node = ScenarioNode.objects.create(slide=locked_slide, node_key='start', is_start=True)
        ending_choice = ScenarioChoice.objects.create(node=start_node, choice_text='End it', next_node=None)

        self.auth_as(self.demo_learner)
        response = self.client.post(
            '/api/scenario-attempts/', {'slide': locked_slide.id, 'path_taken': [ending_choice.id]}
        )
        self.assertEqual(response.status_code, 400)

    # --- Admin demo-lesson-access management endpoints ---

    def test_admin_can_grant_and_revoke_demo_lesson_access(self):
        self.auth_as(self.instructor)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/demo-lesson-access/', {'lesson': self.lesson2.id}
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            DemoLessonAccess.objects.filter(course=self.published_org_course, lesson=self.lesson2).exists()
        )

        response = self.client.delete(
            f'/api/courses/{self.published_org_course.slug}/demo-lesson-access/revoke/',
            {'lesson': self.lesson2.id},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            DemoLessonAccess.objects.filter(course=self.published_org_course, lesson=self.lesson2).exists()
        )

    def test_learner_cannot_manage_demo_lesson_access(self):
        self.auth_as(self.learner)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/demo-lesson-access/', {'lesson': self.lesson2.id}
        )
        self.assertEqual(response.status_code, 403)

    def test_demo_lesson_access_grant_rejects_lesson_from_another_course(self):
        other_module = Module.objects.create(course=self.other_org_course, title='Other', order=1)
        foreign_lesson = Lesson.objects.create(module=other_module, title='Foreign', order=1)
        self.auth_as(self.platform_admin)
        response = self.client.post(
            f'/api/courses/{self.published_org_course.slug}/demo-lesson-access/', {'lesson': foreign_lesson.id}
        )
        self.assertEqual(response.status_code, 404)
