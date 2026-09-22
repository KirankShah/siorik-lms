"""
End-to-end API flow tests for the LMS backend.

Run with:
    python manage.py test test_api_flows
"""
import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from openpyxl import Workbook, load_workbook
from PIL import Image, ImageDraw
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Organization, User
from accounts.services import UserProvisioningError, provision_demo_user
from assessments.models import CategorizeItem, CategoryBucket, Choice, HotspotRegion, Question, Quiz, QuizAttempt, WordBankToken
from assignments.models import Assignment, AssignmentSubmission
from audit.models import AuditLog
from certificates.models import Certificate, CertificateTemplate
from certificates.services import (
    MIN_AUTO_SHRINK_FONT_SIZE,
    CertificateIssuanceError,
    _fit_font,
    _resolve_template,
    certificate_ineligibility_reason,
    generate_certificate,
)
from courses.models import (
    Course,
    CourseAccess,
    DemoLessonAccess,
    Element,
    Enrollment,
    Lesson,
    LessonProgress,
    Module,
    Slide,
    SlideProgress,
)
from courses.learning_path import TIER_COMPLETE_BADGE_KEYS, check_learning_path_milestones
from courses.video_streaming import build_video_stream_token
from gamification.models import Badge, LeaderboardEntry, UserBadge
from gamification.services import (
    COURSE_COMPLETION_POINTS,
    LEVEL_ASSESSMENT_PASS_POINTS,
    STREAK_BADGE_THRESHOLDS,
    award_badges_for_level_assessment_attempt,
    recalculate_leaderboard_entry,
    record_learning_activity,
)
from levelassessments.models import (
    AssessmentLevel,
    LevelAssessmentAnswer,
    LevelAssessmentAttempt,
    LevelChoice,
    LevelQuestion,
    QuestionSet,
)
from levelassessments.services import LevelAssessmentError, normalize_question_text, start_level_assessment_attempt
from narration.models import SlideNarration
from org_settings.models import OrganizationSettings
from org_settings.services import send_due_inactivity_reminders
from resources.models import Resource
from scenarios.models import ScenarioAttempt, ScenarioChoice, ScenarioNode


def configure_assessment_level(organization, name, **config):
    """Every Organization now gets its four AssessmentLevel rows from a
    post_save signal (levelassessments.signals), so tests fetch-and-configure
    the one they want rather than creating it.

    pass_threshold/questions_per_attempt used to be per-level fields; they're
    now org_settings.OrganizationSettings.pass_mark_percent/
    questions_per_attempt (one row per organization, shared by all four of
    its levels) — passed as kwargs here for the same reason (most existing
    call sites just want "this org's pass mark/question count", written back
    when these were per-level), transparently redirected to the org's
    settings row instead of split into a separate call everywhere."""
    level, _ = AssessmentLevel.objects.get_or_create(organization=organization, name=name)

    org_settings_updates = {}
    if 'pass_threshold' in config:
        org_settings_updates['pass_mark_percent'] = config.pop('pass_threshold')
    if 'questions_per_attempt' in config:
        org_settings_updates['questions_per_attempt'] = config.pop('questions_per_attempt')
    if org_settings_updates:
        OrganizationSettings.objects.filter(organization=organization).update(**org_settings_updates)

    for field, value in config.items():
        setattr(level, field, value)
    if config:
        level.save(update_fields=list(config))
    return level


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


def make_test_pdf_upload(filename='doc.pdf', content_type='application/pdf', body=b'fake pdf body'):
    return SimpleUploadedFile(filename, b'%PDF-1.4\n' + body, content_type=content_type)


LEVEL_QUESTION_TEMPLATE_HEADER = [
    'Question Set', 'Question Text', 'Question Type', 'Option A', 'Option B', 'Option C', 'Option D', 'Option E',
    'Correct Answer(s)', 'Marks', 'Explanation', 'Feedback if Correct', 'Feedback if Incorrect',
]


def make_question_template_upload(rows_by_sheet, filename='questions.xlsx'):
    """
    Builds an in-memory .xlsx upload matching the Level Assessment Question
    Template's column structure. `rows_by_sheet` is {sheet_name: [row_tuple, ...]}
    where each row_tuple is 13 values in LEVEL_QUESTION_TEMPLATE_HEADER order.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_name, rows in rows_by_sheet.items():
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(LEVEL_QUESTION_TEMPLATE_HEADER)
        for row in rows:
            sheet.append(list(row))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return SimpleUploadedFile(
        filename, buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


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

    def test_login_updates_last_login(self):
        # rest_framework_simplejwt's TokenObtainPairSerializer never sends
        # Django's user_logged_in signal (it isn't django.contrib.auth.login()),
        # so last_login only updates here because ThrottledTokenObtainPairView
        # calls update_last_login explicitly.
        self.assertIsNone(self.learner.last_login)
        before = timezone.now()

        response = self.client.post('/api/auth/login/', {'email': 'learner@example.com', 'password': 'pass12345'})

        self.assertEqual(response.status_code, 200)
        self.learner.refresh_from_db()
        self.assertIsNotNone(self.learner.last_login)
        self.assertGreaterEqual(self.learner.last_login, before)

    def test_failed_login_does_not_update_last_login(self):
        self.client.post('/api/auth/login/', {'email': 'learner@example.com', 'password': 'wrong'})

        self.learner.refresh_from_db()
        self.assertIsNone(self.learner.last_login)

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
        # An enrollment carries its own course display fields — the learner
        # dashboard's "My Courses" list relies on these instead of
        # cross-referencing GET /api/courses/, since that catalog is
        # path-scoped for a learner with an assigned path and can
        # legitimately omit a course they're still enrolled in.
        self.assertEqual(listing.data[0]['course_title'], self.published_org_course.title)
        self.assertEqual(listing.data[0]['course_slug'], self.published_org_course.slug)
        self.assertEqual(
            listing.data[0]['course_completion_deadline_days'], self.published_org_course.completion_deadline_days
        )

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


class LearningPathApiTests(BaseAPITestCase):
    """GET /api/learning-path/ — the "My Learning Path" dashboard section:
    sequential completed/current/locked gating, per-tier milestone
    completion, and the branch-comparison line."""

    def setUp(self):
        super().setUp()
        self.foundation_1 = Course.objects.create(
            title='Foundation 1', slug='foundation-1', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=1,
        )
        self.foundation_2 = Course.objects.create(
            title='Foundation 2', slug='foundation-2', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=2,
        )
        self.officer_course = Course.objects.create(
            title='Officer Tier Course', slug='officer-tier-course', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=3,
            minimum_assessment_level=User.AssessmentLevel.OFFICER,
        )
        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save(update_fields=['assessment_level'])

    def _tier(self, tiers, tier_key):
        return next(tier for tier in tiers if tier['tier_key'] == tier_key)

    def _state(self, tier, course_id):
        return next(course['state'] for course in tier['courses'] if course['id'] == course_id)

    def test_partial_foundation_progress_states(self):
        Enrollment.objects.create(
            user=self.learner, course=self.foundation_1,
            status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
        )
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')
        self.assertEqual(response.status_code, 200)

        foundation = self._tier(response.data['tiers'], 'FOUNDATION')
        self.assertFalse(foundation['is_complete'])
        self.assertEqual(self._state(foundation, self.foundation_1.id), 'completed')
        self.assertEqual(self._state(foundation, self.foundation_2.id), 'current')

        officer_tier = self._tier(response.data['tiers'], User.AssessmentLevel.OFFICER)
        self.assertFalse(officer_tier['is_complete'])
        self.assertEqual(self._state(officer_tier, self.officer_course.id), 'locked')

    def test_completing_foundation_unlocks_the_next_tier_immediately(self):
        for course in (self.foundation_1, self.foundation_2):
            Enrollment.objects.create(
                user=self.learner, course=course,
                status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
            )
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')

        foundation = self._tier(response.data['tiers'], 'FOUNDATION')
        self.assertTrue(foundation['is_complete'])
        self.assertEqual(self._state(foundation, self.foundation_1.id), 'completed')
        self.assertEqual(self._state(foundation, self.foundation_2.id), 'completed')

        # Unlocking is purely sequential — completing every Foundation
        # course is all it takes for the Officer tier's course to become
        # reachable next.
        officer_tier = self._tier(response.data['tiers'], User.AssessmentLevel.OFFICER)
        self.assertEqual(self._state(officer_tier, self.officer_course.id), 'current')

    def test_course_unlock_is_never_gated_by_a_level_assessment(self):
        # Explicitly confirms the decoupling: even with a FAILED attempt on
        # record (and none ever passed), the next tier's course is still
        # reachable purely because the preceding course is done — passing a
        # Level Assessment is a separate achievement (it gates the single
        # Learning Path Completion Certificate — see certificates.services),
        # never a course-access requirement.
        for course in (self.foundation_1, self.foundation_2):
            Enrollment.objects.create(
                user=self.learner, course=course,
                status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
            )
        officer_level = configure_assessment_level(self.org, User.AssessmentLevel.OFFICER)
        LevelAssessmentAttempt.objects.create(
            user=self.learner, assessment_level=officer_level, passed=False, submitted_at=timezone.now(),
        )
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')

        officer_tier = self._tier(response.data['tiers'], User.AssessmentLevel.OFFICER)
        self.assertEqual(self._state(officer_tier, self.officer_course.id), 'current')

    def test_branch_percentile_computed_from_colleagues_completed_counts(self):
        Enrollment.objects.create(
            user=self.learner, course=self.foundation_1,
            status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
        )
        self.learner.branch_department = 'Retail Banking'
        self.learner.save(update_fields=['branch_department'])

        behind_colleague = User.objects.create_user(
            email='behind@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org, branch_department='Retail Banking',
        )
        ahead_colleague = User.objects.create_user(
            email='ahead@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org, branch_department='retail banking',  # case-insensitive match
        )
        for course in (self.foundation_1, self.foundation_2, self.officer_course):
            Enrollment.objects.create(
                user=ahead_colleague, course=course,
                status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
            )
        # Different branch — must never count towards the comparison.
        User.objects.create_user(
            email='other-branch@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=self.org, branch_department='Compliance',
        )

        self.auth_as(self.learner)
        response = self.client.get('/api/learning-path/')

        # 1 of 2 branch colleagues (behind_colleague) completed fewer path
        # courses than the learner's 1 — exactly 50%, not a placeholder.
        self.assertEqual(response.data['branch_percentile'], 50)

    def test_branch_percentile_omitted_without_a_branch_department(self):
        self.assertIsNone(self.learner.branch_department)
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')

        self.assertIsNone(response.data['branch_percentile'])

    def test_courses_without_path_order_are_excluded_from_the_path(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/learning-path/')

        path_course_ids = {course['id'] for tier in response.data['tiers'] for course in tier['courses']}
        self.assertNotIn(self.published_org_course.id, path_course_ids)


class LearningPathCumulativeTierTests(BaseAPITestCase):
    """
    courses.learning_path._path_courses_for_user's tier membership is
    cumulative (tier_rank "at or below"), matching
    gamification.services.recalculate_leaderboard_entry's scoring — a
    learner's path includes every tier at or below their own
    assessment_level, not just their own exact tier. Mirrors the real
    production shape that motivated this fix: 3 Foundation + 3
    Assistant-Supervisor + 2 Officer + 1 Management courses, and no
    Senior-Management-tier course at all.
    """

    def setUp(self):
        super().setUp()
        self.foundation_courses = [
            Course.objects.create(
                title=f'Foundation {i}', slug=f'cum-foundation-{i}', organization=self.org,
                content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=i,
            )
            for i in range(1, 4)
        ]
        self.assistant_supervisor_courses = [
            Course.objects.create(
                title=f'Assistant-Supervisor {i}', slug=f'cum-as-{i}', organization=self.org,
                content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=3 + i,
                minimum_assessment_level=User.AssessmentLevel.ASSISTANT_SUPERVISOR,
            )
            for i in range(1, 4)
        ]
        self.officer_courses = [
            Course.objects.create(
                title=f'Officer {i}', slug=f'cum-officer-{i}', organization=self.org,
                content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=6 + i,
                minimum_assessment_level=User.AssessmentLevel.OFFICER,
            )
            for i in range(1, 3)
        ]
        self.management_course = Course.objects.create(
            title='Management 1', slug='cum-management-1', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=9,
            minimum_assessment_level=User.AssessmentLevel.MANAGEMENT,
        )
        # No senior_management-tier course exists — mirrors production.

    def _set_level(self, level):
        self.learner.assessment_level = level
        self.learner.save(update_fields=['assessment_level'])

    def _path_course_ids(self, response):
        return [course['id'] for tier in response.data['tiers'] for course in tier['courses']]

    def test_senior_management_sees_all_nine_courses_in_path_order(self):
        self._set_level(User.AssessmentLevel.SENIOR_MANAGEMENT)
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')

        expected_ids = [
            c.id for c in (
                self.foundation_courses
                + self.assistant_supervisor_courses
                + self.officer_courses
                + [self.management_course]
            )
        ]
        self.assertEqual(self._path_course_ids(response), expected_ids)
        self.assertEqual(len(expected_ids), 9)

    def test_management_sees_nine_courses(self):
        # Same 9 as Senior Management here, since no Senior-Management-tier
        # course exists yet — Management is the highest tier with content.
        self._set_level(User.AssessmentLevel.MANAGEMENT)
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')
        self.assertEqual(len(self._path_course_ids(response)), 9)

    def test_officer_sees_eight_courses_excluding_management(self):
        self._set_level(User.AssessmentLevel.OFFICER)
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')
        ids = self._path_course_ids(response)
        self.assertEqual(len(ids), 8)
        self.assertNotIn(self.management_course.id, ids)

    def test_assistant_supervisor_sees_six_courses_excluding_higher_tiers(self):
        self._set_level(User.AssessmentLevel.ASSISTANT_SUPERVISOR)
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')
        ids = self._path_course_ids(response)
        self.assertEqual(len(ids), 6)
        self.assertNotIn(self.officer_courses[0].id, ids)
        self.assertNotIn(self.management_course.id, ids)

    def test_tier_sections_are_grouped_in_ascending_seniority_order(self):
        self._set_level(User.AssessmentLevel.MANAGEMENT)
        self.auth_as(self.learner)

        response = self.client.get('/api/learning-path/')
        tier_keys = [tier['tier_key'] for tier in response.data['tiers']]
        self.assertEqual(
            tier_keys,
            [
                'FOUNDATION',
                User.AssessmentLevel.ASSISTANT_SUPERVISOR,
                User.AssessmentLevel.OFFICER,
                User.AssessmentLevel.MANAGEMENT,
            ],
        )

    def test_lower_tier_course_is_genuinely_reachable_once_unlocked(self):
        # The core regression this fix addresses: a higher-tier learner's
        # lower-tier courses must actually be completable via the real API,
        # not just visible — path_accessible_courses_for_user must grant
        # real access once a course's state is 'current', for every tier.
        self._set_level(User.AssessmentLevel.SENIOR_MANAGEMENT)
        self.auth_as(self.learner)

        first_course = self.foundation_courses[0]
        module = Module.objects.create(course=first_course, title='M1', order=1)
        lesson = Lesson.objects.create(module=module, title='L1', order=1)
        slide = Slide.objects.create(lesson=lesson, order=1, slide_type=Slide.SlideType.CONTENT)

        response = self.client.get(f'/api/courses/{first_course.slug}/')
        self.assertEqual(response.status_code, 200)

        enrollment = Enrollment.objects.create(user=self.learner, course=first_course)
        progress = self.client.post(
            f'/api/enrollments/{enrollment.id}/slide-progress/', {'slide': slide.id, 'completed': True}
        )
        self.assertEqual(progress.status_code, 200)


class LearningPathMilestoneTests(BaseAPITestCase):
    """Tier-completion badges (courses.learning_path.check_learning_path_milestones)
    and the 'milestones' payload slide-progress attaches to its response once
    a path course completes — backs the mascot congratulation + certificate
    reveal moments."""

    def setUp(self):
        super().setUp()
        self.foundation_1 = self._make_single_slide_course('Foundation 1', 'ms-foundation-1', path_order=1)
        self.foundation_2 = self._make_single_slide_course('Foundation 2', 'ms-foundation-2', path_order=2)
        self.officer_course = self._make_single_slide_course(
            'Officer Tier Course', 'ms-officer-course', path_order=3,
            minimum_assessment_level=User.AssessmentLevel.OFFICER,
        )
        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save(update_fields=['assessment_level'])

    def _make_single_slide_course(self, title, slug, path_order, minimum_assessment_level=None):
        course = Course.objects.create(
            title=title, slug=slug, organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
            path_order=path_order, minimum_assessment_level=minimum_assessment_level,
        )
        module = Module.objects.create(course=course, title='M1', order=1)
        lesson = Lesson.objects.create(module=module, title='L1', order=1)
        Slide.objects.create(lesson=lesson, order=1, slide_type=Slide.SlideType.CONTENT)
        return course

    def _complete_course(self, course):
        enrollment, _ = Enrollment.objects.get_or_create(user=self.learner, course=course)
        slide = Slide.objects.get(lesson__module__course=course)
        return self.client.post(
            f'/api/enrollments/{enrollment.id}/slide-progress/', {'slide': slide.id, 'completed': True}
        )

    def earned_keys(self):
        return set(UserBadge.objects.filter(user=self.learner).values_list('badge__key', flat=True))

    def test_completing_a_mid_path_course_awards_no_tier_badge(self):
        self.auth_as(self.learner)
        response = self._complete_course(self.foundation_1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['milestones']['newly_completed_tiers'], [])
        self.assertFalse(response.data['milestones']['path_fully_completed'])
        self.assertEqual(self.earned_keys() & set(TIER_COMPLETE_BADGE_KEYS.values()), set())

    def test_completing_the_whole_tier_awards_its_badge_and_reports_the_milestone(self):
        self.auth_as(self.learner)
        self._complete_course(self.foundation_1)
        response = self._complete_course(self.foundation_2)

        self.assertIn('tier_complete_foundation', self.earned_keys())
        self.assertIn('milestones', response.data)
        newly_completed = response.data['milestones']['newly_completed_tiers']
        self.assertEqual(len(newly_completed), 1)
        self.assertEqual(newly_completed[0]['tier_key'], 'FOUNDATION')
        self.assertEqual(newly_completed[0]['course_count'], 2)
        self.assertFalse(response.data['milestones']['path_fully_completed'])

    def test_completing_the_final_tier_reports_path_fully_completed(self):
        self.auth_as(self.learner)
        self._complete_course(self.foundation_1)
        self._complete_course(self.foundation_2)

        officer_level = configure_assessment_level(self.org, User.AssessmentLevel.OFFICER)
        LevelAssessmentAttempt.objects.create(
            user=self.learner, assessment_level=officer_level, passed=True, submitted_at=timezone.now(),
        )

        response = self._complete_course(self.officer_course)

        newly_completed = response.data['milestones']['newly_completed_tiers']
        self.assertEqual([tier['tier_key'] for tier in newly_completed], [User.AssessmentLevel.OFFICER])
        self.assertTrue(response.data['milestones']['path_fully_completed'])
        self.assertIn('tier_complete_officer', self.earned_keys())

    def test_tier_badge_not_re_awarded_on_repeat_checks(self):
        self.auth_as(self.learner)
        self._complete_course(self.foundation_1)
        self._complete_course(self.foundation_2)
        self.assertEqual(
            UserBadge.objects.filter(user=self.learner, badge__key='tier_complete_foundation').count(), 1
        )

        check_learning_path_milestones(self.learner)

        self.assertEqual(
            UserBadge.objects.filter(user=self.learner, badge__key='tier_complete_foundation').count(), 1
        )


class LearningStreakTests(TestCase):
    """gamification.services.record_learning_activity — streak increment/reset
    and the 3-Day Streak badge, driven directly rather than through the API
    so each day's date is under test control."""

    def setUp(self):
        self.org = Organization.objects.create(name='Acme Bank', slug='acme-bank-streaks')
        self.user = User.objects.create_user(
            email='streaker@example.com', password='pw', role=User.Role.LEARNER, organization=self.org,
        )

    def _record_on(self, day):
        with patch('gamification.services.timezone.localdate', return_value=day):
            record_learning_activity(self.user)
        self.user.refresh_from_db()

    def earned_keys(self):
        return set(UserBadge.objects.filter(user=self.user).values_list('badge__key', flat=True))

    def test_first_ever_activity_sets_streak_to_one(self):
        self._record_on(date(2026, 1, 1))
        self.assertEqual(self.user.current_streak_days, 1)
        self.assertEqual(self.user.last_active_date, date(2026, 1, 1))

    def test_second_call_same_day_is_a_no_op(self):
        self._record_on(date(2026, 1, 1))
        self._record_on(date(2026, 1, 1))
        self.assertEqual(self.user.current_streak_days, 1)

    def test_consecutive_day_increments_streak(self):
        self._record_on(date(2026, 1, 1))
        self._record_on(date(2026, 1, 2))
        self.assertEqual(self.user.current_streak_days, 2)

    def test_skipped_day_resets_streak_to_one(self):
        self._record_on(date(2026, 1, 1))
        self._record_on(date(2026, 1, 2))
        self._record_on(date(2026, 1, 4))  # skipped Jan 3
        self.assertEqual(self.user.current_streak_days, 1)

    def test_streak_badge_awarded_the_first_day_it_reaches_threshold(self):
        streak_threshold = dict(STREAK_BADGE_THRESHOLDS)
        badge_key = next(key for threshold, key in STREAK_BADGE_THRESHOLDS if threshold == 3)
        self.assertIn(3, streak_threshold)  # sanity: the 3-day badge this test drives still exists

        start = date(2026, 1, 1)
        self._record_on(start)
        self.assertNotIn(badge_key, self.earned_keys())
        self._record_on(start + timedelta(days=1))
        self.assertNotIn(badge_key, self.earned_keys())
        self._record_on(start + timedelta(days=2))

        self.assertIn(badge_key, self.earned_keys())
        self.assertEqual(self.user.current_streak_days, 3)

    def test_streak_badge_not_re_awarded_after_reset(self):
        badge_key = next(key for threshold, key in STREAK_BADGE_THRESHOLDS if threshold == 3)
        start = date(2026, 1, 1)
        for offset in range(3):
            self._record_on(start + timedelta(days=offset))
        self.assertEqual(UserBadge.objects.filter(user=self.user, badge__key=badge_key).count(), 1)

        self._record_on(start + timedelta(days=10))  # streak resets to 1
        self.assertEqual(self.user.current_streak_days, 1)
        self.assertEqual(UserBadge.objects.filter(user=self.user, badge__key=badge_key).count(), 1)


class PathAccessEnforcementTests(BaseAPITestCase):
    """
    Server-side denial for a course a learner hasn't reached yet in their own
    Learning Path — courses.permissions.path_accessible_courses_for_user,
    used everywhere a learner's course/lesson content is actually served
    (course detail, slide elements, quizzes, enrollment creation). Confirms
    this is a real permission check, not just the dashboard widget's visual
    treatment.
    """

    def setUp(self):
        super().setUp()
        self.foundation_1 = self._make_course('Foundation 1', 'pe-foundation-1', path_order=1)
        self.foundation_2 = self._make_course('Foundation 2', 'pe-foundation-2', path_order=2)
        self.officer_course = self._make_course(
            'Officer Tier Course', 'pe-officer-course', path_order=3,
            minimum_assessment_level=User.AssessmentLevel.OFFICER,
        )
        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save(update_fields=['assessment_level'])

        # _make_course already created one module/lesson/CONTENT slide for
        # officer_course — reuse that lesson (rather than a second module,
        # which would collide on the (course, order) unique constraint) and
        # add a QUIZ slide alongside it, so there's real quiz content too.
        lesson = Lesson.objects.get(module__course=self.officer_course)
        self.locked_content_slide = Slide.objects.get(lesson=lesson)
        self.locked_quiz_slide = Slide.objects.create(lesson=lesson, order=2, slide_type=Slide.SlideType.QUIZ)
        Quiz.objects.create(slide=self.locked_quiz_slide, title='Locked Quiz', pass_percentage=50)

    def _make_course(self, title, slug, path_order, minimum_assessment_level=None):
        course = Course.objects.create(
            title=title, slug=slug, organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
            path_order=path_order, minimum_assessment_level=minimum_assessment_level,
        )
        module = Module.objects.create(course=course, title='M1', order=1)
        lesson = Lesson.objects.create(module=module, title='L1', order=1)
        Slide.objects.create(lesson=lesson, order=1, slide_type=Slide.SlideType.CONTENT)
        return course

    def test_locked_course_detail_is_denied(self):
        # officer_course is several steps ahead: neither foundation course is
        # complete, and even if they were, the Officer tier assessment
        # hasn't been passed.
        self.auth_as(self.learner)
        response = self.client.get(f'/api/courses/{self.officer_course.slug}/')
        self.assertEqual(response.status_code, 404)

    def test_locked_course_elements_endpoint_returns_nothing(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/elements/?slide={self.locked_content_slide.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_locked_course_quiz_endpoint_returns_nothing(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/quizzes/?slide={self.locked_quiz_slide.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_cannot_enroll_directly_in_a_locked_course(self):
        self.auth_as(self.learner)
        response = self.client.post('/api/enrollments/', {'course': self.officer_course.id})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Enrollment.objects.filter(user=self.learner, course=self.officer_course).exists())

    def test_current_course_remains_accessible(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/courses/{self.foundation_1.slug}/')
        self.assertEqual(response.status_code, 200)

    def test_completed_course_remains_accessible(self):
        Enrollment.objects.create(
            user=self.learner, course=self.foundation_1,
            status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
        )
        self.auth_as(self.learner)
        response = self.client.get(f'/api/courses/{self.foundation_1.slug}/')
        self.assertEqual(response.status_code, 200)

    def test_unlocking_the_tier_grants_real_access(self):
        for course in (self.foundation_1, self.foundation_2):
            Enrollment.objects.create(
                user=self.learner, course=course,
                status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
            )
        officer_level = configure_assessment_level(self.org, User.AssessmentLevel.OFFICER)
        LevelAssessmentAttempt.objects.create(
            user=self.learner, assessment_level=officer_level, passed=True, submitted_at=timezone.now(),
        )
        self.auth_as(self.learner)

        response = self.client.get(f'/api/courses/{self.officer_course.slug}/')
        self.assertEqual(response.status_code, 200)

    def test_admin_bypasses_path_gating_entirely(self):
        self.auth_as(self.org_admin)
        response = self.client.get(f'/api/courses/{self.officer_course.slug}/')
        self.assertEqual(response.status_code, 200)

    def test_course_without_path_order_is_never_path_gated(self):
        self.auth_as(self.learner)
        response = self.client.get(f'/api/courses/{self.published_org_course.slug}/')
        self.assertEqual(response.status_code, 200)


class LevelCourseAssignmentApiTests(BaseAPITestCase):
    """Role-Based Training admin screen (courses.models.LevelCourseAssignment)
    and its exact-level integration with the live learner Learning Path."""

    def setUp(self):
        super().setUp()
        self.assistant_level = configure_assessment_level(self.org, User.AssessmentLevel.ASSISTANT_SUPERVISOR)
        self.officer_level = configure_assessment_level(self.org, User.AssessmentLevel.OFFICER)
        self.management_level = configure_assessment_level(self.org, User.AssessmentLevel.MANAGEMENT)
        self.senior_level = configure_assessment_level(self.org, User.AssessmentLevel.SENIOR_MANAGEMENT)
        self.other_org_level = configure_assessment_level(self.other_org, User.AssessmentLevel.OFFICER)

        self.course_a = Course.objects.create(
            title='Course A', slug='rbt-course-a', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        )
        self.course_b = Course.objects.create(
            title='Course B', slug='rbt-course-b', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        )
        self.course_c = Course.objects.create(
            title='Course C', slug='rbt-course-c', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        )

    def list_url(self, level):
        return f'/api/level-course-assignments/?assessment_level={level.id}'

    # --- Blank starting point / basic assign+list ---

    def test_level_starts_with_zero_assignments_and_full_unassigned_pool(self):
        self.auth_as(self.org_admin)
        response = self.client.get(self.list_url(self.assistant_level))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['assigned'], [])
        # Superset check, not exact equality — BaseAPITestCase.setUp already
        # creates other org-owned courses (published_org_course etc.) that
        # legitimately belong to this same organization's curriculum too.
        unassigned_ids = {c['id'] for c in response.data['unassigned']}
        self.assertTrue({self.course_a.id, self.course_b.id, self.course_c.id}.issubset(unassigned_ids))

    def test_assigning_a_course_appends_it_and_moves_it_out_of_unassigned(self):
        self.auth_as(self.org_admin)
        response = self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.assistant_level.id, 'course': self.course_a.id,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['course_id'], self.course_a.id)
        self.assertEqual(response.data['order'], 1)

        listing = self.client.get(self.list_url(self.assistant_level))
        self.assertEqual([c['course_id'] for c in listing.data['assigned']], [self.course_a.id])
        unassigned_ids = {c['id'] for c in listing.data['unassigned']}
        self.assertTrue({self.course_b.id, self.course_c.id}.issubset(unassigned_ids))
        self.assertNotIn(self.course_a.id, unassigned_ids)

    def test_creating_assignments_for_all_four_levels_from_blank(self):
        self.auth_as(self.org_admin)
        levels = [self.assistant_level, self.officer_level, self.management_level, self.senior_level]
        for level in levels:
            response = self.client.post('/api/level-course-assignments/', {
                'assessment_level': level.id, 'course': self.course_a.id,
            })
            self.assertEqual(response.status_code, 201)

        for level in levels:
            listing = self.client.get(self.list_url(level))
            self.assertEqual([c['course_id'] for c in listing.data['assigned']], [self.course_a.id])

    def test_duplicate_assignment_returns_400_not_500(self):
        self.auth_as(self.org_admin)
        self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.assistant_level.id, 'course': self.course_a.id,
        })
        response = self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.assistant_level.id, 'course': self.course_a.id,
        })
        self.assertEqual(response.status_code, 400)

    # --- Reordering ---

    def test_reorder_persists_new_order(self):
        self.auth_as(self.org_admin)
        for course in [self.course_a, self.course_b, self.course_c]:
            self.client.post('/api/level-course-assignments/', {
                'assessment_level': self.assistant_level.id, 'course': course.id,
            })

        reorder_response = self.client.post('/api/level-course-assignments/reorder/', {
            'assessment_level': self.assistant_level.id,
            'course_ids': [self.course_c.id, self.course_a.id, self.course_b.id],
        }, format='json')
        self.assertEqual(reorder_response.status_code, 200)
        self.assertEqual(
            [c['course_id'] for c in reorder_response.data], [self.course_c.id, self.course_a.id, self.course_b.id],
        )

        listing = self.client.get(self.list_url(self.assistant_level))
        self.assertEqual(
            [c['course_id'] for c in listing.data['assigned']], [self.course_c.id, self.course_a.id, self.course_b.id],
        )

    def test_reorder_rejects_a_course_id_set_that_does_not_match(self):
        self.auth_as(self.org_admin)
        self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.assistant_level.id, 'course': self.course_a.id,
        })
        response = self.client.post('/api/level-course-assignments/reorder/', {
            'assessment_level': self.assistant_level.id,
            'course_ids': [self.course_a.id, self.course_b.id],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    # --- Same course, independent assignment across levels ---

    def test_same_course_can_be_assigned_to_multiple_levels_independently(self):
        self.auth_as(self.org_admin)
        officer_response = self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.officer_level.id, 'course': self.course_a.id,
        })
        management_response = self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.management_level.id, 'course': self.course_a.id,
        })
        self.assertEqual(officer_response.status_code, 201)
        self.assertEqual(management_response.status_code, 201)

        officer_listing = self.client.get(self.list_url(self.officer_level))
        management_listing = self.client.get(self.list_url(self.management_level))
        self.assertEqual([c['course_id'] for c in officer_listing.data['assigned']], [self.course_a.id])
        self.assertEqual([c['course_id'] for c in management_listing.data['assigned']], [self.course_a.id])

        # Removing it from one level leaves the other untouched.
        assignment_id = officer_listing.data['assigned'][0]['id']
        delete_response = self.client.delete(f'/api/level-course-assignments/{assignment_id}/')
        self.assertEqual(delete_response.status_code, 204)

        officer_listing_after = self.client.get(self.list_url(self.officer_level))
        management_listing_after = self.client.get(self.list_url(self.management_level))
        self.assertEqual(officer_listing_after.data['assigned'], [])
        self.assertEqual([c['course_id'] for c in management_listing_after.data['assigned']], [self.course_a.id])

    # --- Delete doesn't touch the Course itself ---

    def test_unassigning_deletes_only_the_assignment_not_the_course(self):
        self.auth_as(self.org_admin)
        create_response = self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.assistant_level.id, 'course': self.course_a.id,
        })
        assignment_id = create_response.data['id']

        self.client.delete(f'/api/level-course-assignments/{assignment_id}/')

        self.assertTrue(Course.objects.filter(id=self.course_a.id).exists())
        listing = self.client.get(self.list_url(self.assistant_level))
        self.assertEqual(listing.data['assigned'], [])
        self.assertIn(self.course_a.id, {c['id'] for c in listing.data['unassigned']})

    # --- Permissions/scoping ---

    def test_org_admin_cannot_manage_another_organizations_level(self):
        self.auth_as(self.org_admin)
        response = self.client.get(self.list_url(self.other_org_level))
        self.assertEqual(response.status_code, 403)

    def test_platform_admin_can_manage_any_organizations_level(self):
        self.auth_as(self.platform_admin)
        response = self.client.get(self.list_url(self.other_org_level))
        self.assertEqual(response.status_code, 200)

    def test_instructor_is_forbidden(self):
        self.auth_as(self.instructor)
        response = self.client.get(self.list_url(self.assistant_level))
        self.assertEqual(response.status_code, 403)

    def test_learner_is_forbidden(self):
        self.auth_as(self.learner)
        response = self.client.get(self.list_url(self.assistant_level))
        self.assertEqual(response.status_code, 403)

    def test_cannot_assign_a_course_from_another_organization(self):
        other_org_course = Course.objects.create(
            title='Other Org Course For RBT', slug='rbt-other-org-course', organization=self.other_org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        )
        self.auth_as(self.org_admin)
        response = self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.assistant_level.id, 'course': other_org_course.id,
        })
        self.assertEqual(response.status_code, 404)

    # --- Live Learning Path integration ---

    def test_assignments_define_the_exact_live_path_in_configured_order(self):
        self.auth_as(self.org_admin)
        for course in (self.course_c, self.course_a):
            self.client.post('/api/level-course-assignments/', {
                'assessment_level': self.assistant_level.id, 'course': course.id,
            })

        self.learner.assessment_level = User.AssessmentLevel.ASSISTANT_SUPERVISOR
        self.learner.save(update_fields=['assessment_level'])

        self.auth_as(self.learner)
        response = self.client.get('/api/learning-path/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([tier['tier_key'] for tier in response.data['tiers']], [User.AssessmentLevel.ASSISTANT_SUPERVISOR])
        path_courses = response.data['tiers'][0]['courses']
        self.assertEqual([course['id'] for course in path_courses], [self.course_c.id, self.course_a.id])
        self.assertEqual([course['path_order'] for course in path_courses], [1, 2])
        self.assertNotIn(self.course_b.id, {course['id'] for course in path_courses})

    def test_different_levels_receive_only_their_own_assignments(self):
        self.auth_as(self.org_admin)
        self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.assistant_level.id, 'course': self.course_a.id,
        })
        self.client.post('/api/level-course-assignments/', {
            'assessment_level': self.officer_level.id, 'course': self.course_b.id,
        })

        self.learner.assessment_level = User.AssessmentLevel.ASSISTANT_SUPERVISOR
        self.learner.save(update_fields=['assessment_level'])
        self.auth_as(self.learner)
        assistant_path = self.client.get('/api/learning-path/')
        self.assertEqual(
            [course['id'] for tier in assistant_path.data['tiers'] for course in tier['courses']],
            [self.course_a.id],
        )

        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save(update_fields=['assessment_level'])
        officer_path = self.client.get('/api/learning-path/')
        self.assertEqual(
            [course['id'] for tier in officer_path.data['tiers'] for course in tier['courses']],
            [self.course_b.id],
        )

    def test_reordering_assignments_immediately_reorders_the_live_path(self):
        self.auth_as(self.org_admin)
        for course in (self.course_a, self.course_b):
            self.client.post('/api/level-course-assignments/', {
                'assessment_level': self.management_level.id, 'course': course.id,
            })
        self.client.post('/api/level-course-assignments/reorder/', {
            'assessment_level': self.management_level.id,
            'course_ids': [self.course_b.id, self.course_a.id],
        }, format='json')

        self.learner.assessment_level = User.AssessmentLevel.MANAGEMENT
        self.learner.save(update_fields=['assessment_level'])
        self.auth_as(self.learner)
        response = self.client.get('/api/learning-path/')
        self.assertEqual(
            [course['id'] for tier in response.data['tiers'] for course in tier['courses']],
            [self.course_b.id, self.course_a.id],
        )

    def test_learner_course_catalog_matches_the_assigned_path_and_order(self):
        self.auth_as(self.org_admin)
        for course in (self.course_c, self.course_a):
            self.client.post('/api/level-course-assignments/', {
                'assessment_level': self.senior_level.id, 'course': course.id,
            })

        self.learner.assessment_level = User.AssessmentLevel.SENIOR_MANAGEMENT
        self.learner.save(update_fields=['assessment_level'])
        self.auth_as(self.learner)
        response = self.client.get('/api/courses/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([course['id'] for course in response.data], [self.course_c.id, self.course_a.id])


class LearnerCatalogPathViewTests(BaseAPITestCase):
    """GET /api/courses/ (the general Courses catalog) for a LEARNER — must
    match the Learning Path widget exactly once a path is assigned (same
    courses, same path_order sequence, same lock states), and fall back to
    the ordinary full catalog for a learner with no path assigned yet."""

    def setUp(self):
        super().setUp()
        self.foundation_1 = Course.objects.create(
            title='Foundation 1', slug='cat-foundation-1', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=1,
        )
        self.foundation_2 = Course.objects.create(
            title='Foundation 2', slug='cat-foundation-2', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=2,
        )

    def test_catalog_falls_back_to_full_listing_without_a_path(self):
        # A learner in an org where no course has path_order set at all —
        # the catalog should behave exactly as it did before this feature,
        # not show an empty page.
        other_org = Organization.objects.create(name='No Path Org', slug='no-path-org')
        pathless_course = Course.objects.create(
            title='Pathless', slug='pathless-course', organization=other_org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        )
        pathless_learner = User.objects.create_user(
            email='pathless@example.com', password='pass12345',
            role=User.Role.LEARNER, organization=other_org,
        )
        self.auth_as(pathless_learner)

        response = self.client.get('/api/courses/')

        self.assertEqual(response.status_code, 200)
        returned_ids = {course['id'] for course in response.data}
        self.assertIn(pathless_course.id, returned_ids)
        self.assertTrue(all(course['path_state'] is None for course in response.data))

    def test_catalog_shows_only_path_courses_in_path_order_with_matching_states(self):
        Enrollment.objects.create(
            user=self.learner, course=self.foundation_1,
            status=Enrollment.Status.COMPLETED, completed_at=timezone.now(),
        )
        self.auth_as(self.learner)

        catalog_response = self.client.get('/api/courses/')
        path_response = self.client.get('/api/learning-path/')

        self.assertEqual(catalog_response.status_code, 200)
        returned_ids = [course['id'] for course in catalog_response.data]
        # Only the two path courses — not published_org_course/platform_course/
        # etc. from BaseAPITestCase, none of which have a path_order.
        self.assertEqual(returned_ids, [self.foundation_1.id, self.foundation_2.id])

        widget_states = {
            course['id']: course['state']
            for tier in path_response.data['tiers']
            for course in tier['courses']
        }
        catalog_states = {course['id']: course['path_state'] for course in catalog_response.data}
        self.assertEqual(catalog_states, widget_states)
        self.assertEqual(catalog_states[self.foundation_1.id], 'completed')
        self.assertEqual(catalog_states[self.foundation_2.id], 'current')

    def test_admin_catalog_is_unaffected_by_learner_path_scoping(self):
        self.auth_as(self.org_admin)
        response = self.client.get('/api/courses/')
        returned_ids = {course['id'] for course in response.data}
        # Sees the org's ordinary courses, not narrowed to path courses only.
        self.assertIn(self.published_org_course.id, returned_ids)
        self.assertTrue(all(course['path_state'] is None for course in response.data))


class EnrollmentRetakeTests(BaseAPITestCase):
    """"Retake Course" (CourseCompletionModal.tsx) resets an enrollment to a
    fresh state — progress, quiz attempts (so max_attempts starts over), and
    every other attempt type, scoped to just this user+course."""

    def setUp(self):
        super().setUp()
        self.enrollment = Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED, progress_percent=100,
            completed_at=timezone.now(),
        )
        SlideProgress.objects.create(enrollment=self.enrollment, slide=self.quiz_slide, completed_at=timezone.now())
        LessonProgress.objects.create(enrollment=self.enrollment, lesson=self.lesson1, completed_at=timezone.now())
        # Exhaust max_attempts (2) so we can prove a retake actually frees it up.
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=False, score_percent=0)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=2, passed=False, score_percent=0)

        scenario_slide = Slide.objects.create(
            lesson=self.lesson2, order=1, title='Scenario', slide_type=Slide.SlideType.SCENARIO,
        )
        node = ScenarioNode.objects.create(slide=scenario_slide, node_key='start', is_start=True)
        ScenarioAttempt.objects.create(enrollment=self.enrollment, slide=scenario_slide, path_taken=[node.id])

        assignment_slide = Slide.objects.create(
            lesson=self.lesson2, order=2, title='Assignment', slide_type=Slide.SlideType.ASSIGNMENT,
        )
        assignment = Assignment.objects.create(slide=assignment_slide)
        AssignmentSubmission.objects.create(assignment=assignment, user=self.learner, text_response='done')

        # A different course's data for the same learner must survive untouched.
        self.other_enrollment = Enrollment.objects.create(user=self.learner, course=self.platform_course)
        other_module = Module.objects.create(course=self.platform_course, title='M', order=1)
        other_lesson = Lesson.objects.create(module=other_module, title='L', order=1)
        other_quiz_slide = Slide.objects.create(lesson=other_lesson, order=1, title='Q', slide_type=Slide.SlideType.QUIZ)
        self.other_quiz = Quiz.objects.create(slide=other_quiz_slide, title='Q', pass_percentage=50)
        QuizAttempt.objects.create(user=self.learner, quiz=self.other_quiz, attempt_number=1, passed=True, score_percent=100)

    def test_retake_resets_enrollment_and_deletes_all_progress_and_attempts(self):
        self.auth_as(self.learner)
        response = self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'NOT_STARTED')
        self.assertEqual(response.data['progress_percent'], 0)
        self.assertIsNone(response.data['completed_at'])

        self.assertFalse(SlideProgress.objects.filter(enrollment=self.enrollment).exists())
        self.assertFalse(LessonProgress.objects.filter(enrollment=self.enrollment).exists())
        self.assertFalse(QuizAttempt.objects.filter(user=self.learner, quiz=self.quiz).exists())
        self.assertFalse(ScenarioAttempt.objects.filter(enrollment=self.enrollment).exists())
        self.assertFalse(AssignmentSubmission.objects.filter(user=self.learner).filter(assignment__slide__lesson=self.lesson2).exists())

    def test_retake_lets_learner_exceed_the_old_max_attempts(self):
        self.auth_as(self.learner)
        self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')

        payload = [{'question': self.q1.id, 'selected_choices': [self.q1_right.id]},
                   {'question': self.q2.id, 'selected_choices': [self.q2_right.id]}]
        response = self.client.post(f'/api/quizzes/{self.quiz.id}/submit/', {'answers': payload}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(QuizAttempt.objects.filter(user=self.learner, quiz=self.quiz).count(), 1)

    def test_retake_does_not_touch_a_different_course(self):
        self.auth_as(self.learner)
        self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')

        self.other_enrollment.refresh_from_db()
        self.assertTrue(QuizAttempt.objects.filter(user=self.learner, quiz=self.other_quiz).exists())

    def test_other_learner_cannot_retake_someone_elses_enrollment(self):
        self.auth_as(self.other_org_learner)
        response = self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
        self.assertEqual(response.status_code, 404)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'COMPLETED')

    def test_retake_count_increments_and_is_unlimited_by_default(self):
        self.auth_as(self.learner)
        for expected_count in (1, 2, 3):
            response = self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['retake_count'], expected_count)
            self.assertFalse(response.data['retake_limit_reached'])

    def test_max_course_retake_attempts_blocks_further_retakes_once_reached(self):
        OrganizationSettings.objects.filter(organization=self.org).update(max_course_retake_attempts=2)
        self.auth_as(self.learner)

        first = self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.data['retake_limit_reached'])

        second = self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['retake_count'], 2)
        self.assertTrue(second.data['retake_limit_reached'])

        third = self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
        self.assertEqual(third.status_code, 400)
        self.assertIn('maximum', third.data['detail'].lower())

        # Refused, not silently reset — progress from before the blocked
        # attempt is untouched.
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.retake_count, 2)

    def test_a_different_enrollment_for_the_same_org_shares_the_same_cap_independently(self):
        # Each enrollment counts its own retakes — the cap is a per-org rule
        # applied per enrollment, not a shared budget across courses.
        OrganizationSettings.objects.filter(organization=self.org).update(max_course_retake_attempts=1)
        self.auth_as(self.learner)

        self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
        blocked = self.client.post(f'/api/enrollments/{self.enrollment.id}/retake/')
        self.assertEqual(blocked.status_code, 400)

        other_response = self.client.post(f'/api/enrollments/{self.other_enrollment.id}/retake/')
        self.assertEqual(other_response.status_code, 200)


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
        # Learner-facing display title — not course_title, since this
        # certificate represents completing a whole Learning Path, not one
        # course. Fixed and identical for every learner regardless of tier.
        self.assertEqual(
            retrieve.data['title'], 'Certificate of Competency in AML/CFT and Financial Crime Compliance'
        )

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
    """
    POST /api/certificates/issue/ — takes no arguments and grants the
    learner's single Learning Path Completion Certificate once (a) every
    course in their path is completed and meets its own quiz-average
    threshold, and (b) their assigned Level Assessment (if any) has been
    passed. Per-course certificates no longer exist.
    """

    def setUp(self):
        super().setUp()
        self.foundation_1 = self._make_single_slide_course('Foundation 1', 'cert-foundation-1', path_order=1)
        self.foundation_2 = self._make_single_slide_course('Foundation 2', 'cert-foundation-2', path_order=2)

    def _make_single_slide_course(self, title, slug, path_order, minimum_assessment_level=None):
        course = Course.objects.create(
            title=title, slug=slug, organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
            path_order=path_order, minimum_assessment_level=minimum_assessment_level,
        )
        module = Module.objects.create(course=course, title='M1', order=1)
        lesson = Lesson.objects.create(module=module, title='L1', order=1)
        Slide.objects.create(lesson=lesson, order=1, slide_type=Slide.SlideType.CONTENT)
        return course

    def _complete_via_api(self, course):
        enrollment, _ = Enrollment.objects.get_or_create(user=self.learner, course=course)
        slide = Slide.objects.get(lesson__module__course=course)
        return self.client.post(
            f'/api/enrollments/{enrollment.id}/slide-progress/', {'slide': slide.id, 'completed': True}
        )

    def test_issue_endpoint_rejects_when_no_path_is_assigned(self):
        self.auth_as(self.other_org_learner)  # no path-ordered courses at all in their org
        response = self.client.post('/api/certificates/issue/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('No Learning Path', response.data['detail'])

    def test_issue_endpoint_rejects_before_the_whole_path_is_complete(self):
        self.auth_as(self.learner)
        self._complete_via_api(self.foundation_1)  # only one of two path courses done

        response = self.client.post('/api/certificates/issue/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('has not been completed yet', response.data['detail'])

    def test_issue_endpoint_grants_certificate_once_whole_path_is_complete(self):
        self.auth_as(self.learner)
        self._complete_via_api(self.foundation_1)
        self._complete_via_api(self.foundation_2)

        response = self.client.post('/api/certificates/issue/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('certificate_number', response.data)
        self.assertTrue(response.data['pdf_file'])

    def test_issue_endpoint_is_idempotent(self):
        self.auth_as(self.learner)
        self._complete_via_api(self.foundation_1)
        self._complete_via_api(self.foundation_2)

        first = self.client.post('/api/certificates/issue/')
        second = self.client.post('/api/certificates/issue/')
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(Certificate.objects.filter(user=self.learner).count(), 1)

    def test_issue_endpoint_requires_passing_the_assigned_level_assessment(self):
        officer_course = self._make_single_slide_course(
            'Officer Course', 'cert-officer-course', path_order=3,
            minimum_assessment_level=User.AssessmentLevel.OFFICER,
        )
        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save(update_fields=['assessment_level'])

        self.auth_as(self.learner)
        self._complete_via_api(self.foundation_1)
        self._complete_via_api(self.foundation_2)
        # officer_course is still locked (tier assessment not yet passed),
        # so the whole path can't be complete yet either way.
        response = self.client.post('/api/certificates/issue/')
        self.assertEqual(response.status_code, 400)

        officer_level = configure_assessment_level(self.org, User.AssessmentLevel.OFFICER)
        LevelAssessmentAttempt.objects.create(
            user=self.learner, assessment_level=officer_level, passed=True, submitted_at=timezone.now(),
        )
        self._complete_via_api(officer_course)

        response = self.client.post('/api/certificates/issue/')
        self.assertEqual(response.status_code, 200)


class CourseAverageCertificateEligibilityTests(BaseAPITestCase):
    """
    Phase 34: certificate eligibility is governed by the course-wide AVERAGE
    score across all of the course's quizzes (each quiz's own best attempt),
    not a requirement that every individual quiz independently score above
    its own Quiz.pass_percentage. self.quiz (pass_percentage=50) already
    exists on lesson1 from BaseAPITestCase; a second quiz (pass_percentage=
    70) is added on lesson2 here so the average can diverge from any single
    quiz's individual pass/fail outcome. self.learner's organization
    (self.org)'s OrganizationSettings.pass_mark_percent is the default (70)
    — see OrganizationSettingsCertificateThresholdTests below for coverage
    of a *changed* pass_mark_percent actually moving this outcome.
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
        # (Endpoint-level issuance is exercised in CertificateIssueEndpointTests
        # now that a single certificate requires the learner's WHOLE Learning
        # Path, not just this one course — orthogonal to the average-vs-
        # threshold math this class is about.)

        self.assertIsNone(certificate_ineligibility_reason(self.learner, self.published_org_course))

    def test_certificate_denied_when_average_below_threshold_despite_one_quiz_individually_passed(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=False, score_percent=20)
        # Average = (100 + 20) / 2 = 60, below the 70% threshold — even though
        # self.quiz was individually passed against its own pass_percentage=50.

        reason = certificate_ineligibility_reason(self.learner, self.published_org_course)
        self.assertIsNotNone(reason)
        self.assertIn('60.0%', reason)

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

    def test_certificate_eligible_when_average_is_exactly_the_70_percent_threshold(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=70)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=True, score_percent=70)
        # Average = (70 + 70) / 2 = 70.0 — the boundary itself. Eligibility is
        # "at or above" the threshold, so this must be eligible, not blocked.

        self.assertIsNone(certificate_ineligibility_reason(self.learner, self.published_org_course))

    def test_certificate_ineligible_when_average_is_just_below_the_70_percent_threshold(self):
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=70)
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz2, attempt_number=1, passed=False, score_percent=Decimal('69.8'))
        # Average = (70 + 69.8) / 2 = 69.9 — one tenth of a point under the
        # boundary, so this must be ineligible.

        reason = certificate_ineligibility_reason(self.learner, self.published_org_course)
        self.assertIsNotNone(reason)
        self.assertIn('69.9%', reason)


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

    def test_cannot_create_organization_with_duplicate_name(self):
        self.auth_as(self.platform_admin)
        response = self.client.post('/api/organizations/', {'name': self.org.name.upper()})
        self.assertEqual(response.status_code, 400)
        self.assertIn('already exists', str(response.data))

    def test_platform_admin_can_delete_empty_organization(self):
        empty_org = Organization.objects.create(name='Empty Org', slug='empty-org')
        self.auth_as(self.platform_admin)
        response = self.client.delete(f'/api/organizations/{empty_org.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Organization.objects.filter(id=empty_org.id).exists())

    def test_deleting_organization_cascades_its_users_and_own_courses(self):
        # A PLATFORM-owned course can have Course.organization set as inert
        # metadata (ignored for access control there) — it must survive,
        # just unlinked, not be deleted along with the organization.
        tagged_platform_course = Course.objects.create(
            title='Platform Tagged', slug='platform-tagged', organization=self.org,
            content_owner=Course.ContentOwner.PLATFORM, is_published=True,
        )

        self.auth_as(self.platform_admin)
        response = self.client.delete(f'/api/organizations/{self.org.id}/')
        self.assertEqual(response.status_code, 204)

        self.assertFalse(Organization.objects.filter(id=self.org.id).exists())
        self.assertFalse(User.objects.filter(id__in=[self.learner.id, self.org_admin.id, self.instructor.id]).exists())
        self.assertFalse(
            Course.objects.filter(id__in=[self.published_org_course.id, self.unpublished_org_course.id]).exists()
        )
        tagged_platform_course.refresh_from_db()
        self.assertIsNone(tagged_platform_course.organization_id)

    def test_org_admin_cannot_delete_organization(self):
        empty_org = Organization.objects.create(name='Empty Org 2', slug='empty-org-2')
        self.auth_as(self.org_admin)
        response = self.client.delete(f'/api/organizations/{empty_org.id}/')
        self.assertEqual(response.status_code, 403)


class LearnerDeletionTests(BaseAPITestCase):
    def test_platform_admin_can_delete_a_learner(self):
        self.auth_as(self.platform_admin)
        response = self.client.delete(f'/api/learners/{self.learner.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(id=self.learner.id).exists())

    def test_org_admin_cannot_delete_a_learner(self):
        self.auth_as(self.org_admin)
        response = self.client.delete(f'/api/learners/{self.learner.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(id=self.learner.id).exists())

    def test_cannot_delete_a_non_learner_via_this_endpoint(self):
        self.auth_as(self.platform_admin)
        response = self.client.delete(f'/api/learners/{self.instructor.id}/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(id=self.instructor.id).exists())


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


class CourseCloneTests(BaseAPITestCase):
    """Covers courses.services.clone_course via the /clone/ endpoint,
    exercising one slide of every type so every deep-copy branch runs."""

    def setUp(self):
        super().setUp()
        self.module = Module.objects.create(course=self.platform_course, title='Module 1', order=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson 1', order=1, estimated_minutes=5)

        self.content_slide = Slide.objects.create(lesson=self.lesson, order=1, slide_type=Slide.SlideType.CONTENT)
        Element.objects.create(slide=self.content_slide, order=1, element_type=Element.ElementType.TEXT, rich_text='Hello')
        SlideNarration.objects.create(
            slide=self.content_slide, language='en', script_text='Hello there.', voice_name='en-US-JennyNeural',
        )

        self.quiz_slide2 = Slide.objects.create(lesson=self.lesson, order=2, slide_type=Slide.SlideType.QUIZ)
        quiz = Quiz.objects.create(slide=self.quiz_slide2, title='Quiz', pass_percentage=60)
        question = Question.objects.create(
            quiz=quiz, question_text='Categorize this', order=1, question_type=Question.QuestionType.CATEGORIZE,
        )
        bucket = CategoryBucket.objects.create(question=question, label='Bucket A', order=1)
        CategorizeItem.objects.create(question=question, item_text='Item 1', correct_bucket=bucket, order=1)
        HotspotRegion.objects.create(question=question, x=1, y=1, width=10, height=10, is_correct=True)
        WordBankToken.objects.create(question=question, text='word', correct_blank_index=1, order=1)
        Choice.objects.create(question=question, choice_text='Option', is_correct=True, order=1)

        self.assignment_slide = Slide.objects.create(lesson=self.lesson, order=3, slide_type=Slide.SlideType.ASSIGNMENT)
        Assignment.objects.create(slide=self.assignment_slide, instructions='Do it', max_marks=50)

        self.scenario_slide = Slide.objects.create(lesson=self.lesson, order=4, slide_type=Slide.SlideType.SCENARIO)
        start_node = ScenarioNode.objects.create(slide=self.scenario_slide, node_key='start', is_start=True)
        end_node = ScenarioNode.objects.create(slide=self.scenario_slide, node_key='end')
        ScenarioChoice.objects.create(node=start_node, choice_text='Go', next_node=end_node, order=1)
        ScenarioChoice.objects.create(node=start_node, choice_text='Stop', next_node=None, order=2)

    def test_platform_admin_can_clone_course_into_organization(self):
        CourseAccess.objects.create(course=self.platform_course, organization=self.org)
        self.auth_as(self.platform_admin)

        response = self.client.post(f'/api/courses/{self.platform_course.slug}/clone/', {'organization': self.org.id})
        self.assertEqual(response.status_code, 201)

        cloned = Course.objects.get(slug=response.data['slug'])
        self.assertEqual(cloned.content_owner, Course.ContentOwner.ORGANIZATION)
        self.assertEqual(cloned.organization_id, self.org.id)
        self.assertEqual(cloned.cloned_from_id, self.platform_course.id)
        self.assertFalse(cloned.is_published)
        self.assertNotEqual(cloned.id, self.platform_course.id)

        cloned_lesson = Lesson.objects.get(module__course=cloned)
        self.assertEqual(Slide.objects.filter(lesson=cloned_lesson).count(), 4)

        cloned_content_slide = Slide.objects.get(lesson=cloned_lesson, order=1)
        self.assertEqual(cloned_content_slide.elements.count(), 1)
        self.assertEqual(cloned_content_slide.elements.first().rich_text, 'Hello')
        cloned_narration = SlideNarration.objects.get(slide=cloned_content_slide, language='en')
        self.assertEqual(cloned_narration.script_text, 'Hello there.')
        self.assertEqual(cloned_narration.voice_name, 'en-US-JennyNeural')

        cloned_quiz_slide = Slide.objects.get(lesson=cloned_lesson, order=2)
        cloned_question = Question.objects.get(quiz__slide=cloned_quiz_slide)
        self.assertEqual(cloned_question.buckets.count(), 1)
        self.assertEqual(cloned_question.categorize_items.count(), 1)
        self.assertEqual(cloned_question.categorize_items.first().correct_bucket.question_id, cloned_question.id)
        self.assertEqual(cloned_question.hotspot_regions.count(), 1)
        self.assertEqual(cloned_question.word_bank_tokens.count(), 1)
        self.assertEqual(cloned_question.choices.count(), 1)

        cloned_assignment_slide = Slide.objects.get(lesson=cloned_lesson, order=3)
        self.assertEqual(cloned_assignment_slide.assignment.max_marks, 50)

        cloned_scenario_slide = Slide.objects.get(lesson=cloned_lesson, order=4)
        cloned_start = ScenarioNode.objects.get(slide=cloned_scenario_slide, node_key='start')
        cloned_end = ScenarioNode.objects.get(slide=cloned_scenario_slide, node_key='end')
        self.assertEqual(cloned_start.choices.count(), 2)
        self.assertEqual(cloned_start.choices.get(choice_text='Go').next_node_id, cloned_end.id)
        self.assertIsNone(cloned_start.choices.get(choice_text='Stop').next_node_id)

        # Source course is untouched.
        self.assertEqual(Slide.objects.filter(lesson=self.lesson).count(), 4)
        self.assertFalse(CourseAccess.objects.filter(course=self.platform_course, organization=self.org).exists())

    def test_org_admin_cannot_clone_platform_course(self):
        self.auth_as(self.org_admin)
        response = self.client.post(f'/api/courses/{self.platform_course.slug}/clone/', {'organization': self.org.id})
        self.assertEqual(response.status_code, 404)

    def test_platform_admin_can_clone_org_course_into_platform_library(self):
        # First fork the rich platform course into the org so there's an
        # ORGANIZATION-owned course carrying one slide of every type.
        self.auth_as(self.platform_admin)
        org_clone = self.client.post(
            f'/api/courses/{self.platform_course.slug}/clone/', {'organization': self.org.id}
        )
        org_course = Course.objects.get(slug=org_clone.data['slug'])

        response = self.client.post(f'/api/courses/{org_course.slug}/clone/')
        self.assertEqual(response.status_code, 201)

        platform_copy = Course.objects.get(slug=response.data['slug'])
        self.assertEqual(platform_copy.content_owner, Course.ContentOwner.PLATFORM)
        self.assertIsNone(platform_copy.organization_id)
        self.assertEqual(platform_copy.cloned_from_id, org_course.id)
        self.assertFalse(platform_copy.is_published)
        self.assertNotIn(platform_copy.id, (org_course.id, self.platform_course.id))

        copied_lesson = Lesson.objects.get(module__course=platform_copy)
        self.assertEqual(Slide.objects.filter(lesson=copied_lesson).count(), 4)
        copied_question = Question.objects.get(quiz__slide__lesson=copied_lesson)
        self.assertEqual(copied_question.categorize_items.first().correct_bucket.question_id, copied_question.id)

        # Both source courses are untouched.
        self.assertEqual(Slide.objects.filter(lesson__module__course=org_course).count(), 4)
        self.assertEqual(Slide.objects.filter(lesson=self.lesson).count(), 4)

    def test_org_admin_cannot_clone_own_course_into_platform_library(self):
        self.auth_as(self.org_admin)
        response = self.client.post(f'/api/courses/{self.published_org_course.slug}/clone/')
        self.assertEqual(response.status_code, 403)

    def test_platform_admin_can_duplicate_platform_course_in_place(self):
        self.auth_as(self.platform_admin)

        response = self.client.post(f'/api/courses/{self.platform_course.slug}/duplicate/')
        self.assertEqual(response.status_code, 201)

        copy = Course.objects.get(slug=response.data['slug'])
        self.assertNotEqual(copy.id, self.platform_course.id)
        self.assertEqual(copy.content_owner, Course.ContentOwner.PLATFORM)
        self.assertIsNone(copy.organization_id)
        self.assertEqual(copy.title, f'{self.platform_course.title} (Copy)')
        self.assertEqual(copy.cloned_from_id, self.platform_course.id)
        self.assertFalse(copy.is_published)

        copied_lesson = Lesson.objects.get(module__course=copy)
        self.assertEqual(Slide.objects.filter(lesson=copied_lesson).count(), 4)
        copied_question = Question.objects.get(quiz__slide__lesson=copied_lesson)
        self.assertEqual(copied_question.categorize_items.first().correct_bucket.question_id, copied_question.id)

        # Source untouched.
        self.assertEqual(Slide.objects.filter(lesson=self.lesson).count(), 4)

    def test_platform_admin_can_duplicate_org_course_for_same_org(self):
        self.auth_as(self.platform_admin)
        org_clone = self.client.post(
            f'/api/courses/{self.platform_course.slug}/clone/', {'organization': self.org.id}
        )
        org_course = Course.objects.get(slug=org_clone.data['slug'])

        response = self.client.post(f'/api/courses/{org_course.slug}/duplicate/')
        self.assertEqual(response.status_code, 201)

        copy = Course.objects.get(slug=response.data['slug'])
        self.assertEqual(copy.content_owner, Course.ContentOwner.ORGANIZATION)
        self.assertEqual(copy.organization_id, self.org.id)
        self.assertNotIn(copy.id, (org_course.id, self.platform_course.id))
        self.assertEqual(Slide.objects.filter(lesson__module__course=copy).count(), 4)

    def test_org_admin_cannot_duplicate_course(self):
        self.auth_as(self.org_admin)
        response = self.client.post(f'/api/courses/{self.published_org_course.slug}/duplicate/')
        self.assertEqual(response.status_code, 403)


def make_test_image_upload(filename='img.png', color='white'):
    buffer = io.BytesIO()
    Image.new('RGB', (20, 20), color=color).save(buffer, format='PNG')
    return SimpleUploadedFile(filename, buffer.getvalue(), content_type='image/png')


class CourseCloneFileIndependenceTests(BaseAPITestCase):
    """
    Every File/ImageField clone_course/copy_lesson touch (Course.cover_image,
    Lesson.content_file, Element.file/video_file, SlideNarration.audio_file,
    Question.image, CategorizeItem.item_image, ScenarioNode.prompt_image) must
    come out of a clone as a genuinely independent storage object — never a
    reference to the exact same underlying file the source row points at.
    Passing a source FieldFile straight into .objects.create() only copies
    its storage path/name, not its bytes, which is exactly the bug this
    covers (see courses.services._deep_copy_file).
    """

    def setUp(self):
        super().setUp()
        self.platform_course.cover_image = make_test_image_upload('cover.png', color='red')
        self.platform_course.save()

        self.module = Module.objects.create(course=self.platform_course, title='Module 1', order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title='Lesson 1', order=1, estimated_minutes=5,
            lesson_type='DOCUMENT',
            content_file=SimpleUploadedFile('lesson.pdf', b'%PDF-1.4\nlesson content', content_type='application/pdf'),
        )

        self.content_slide = Slide.objects.create(lesson=self.lesson, order=1, slide_type=Slide.SlideType.CONTENT)
        self.element = Element.objects.create(
            slide=self.content_slide, order=1, element_type=Element.ElementType.VIDEO_AUDIO,
            video_file=SimpleUploadedFile('episode.mp4', b'fake video bytes', content_type='video/mp4'),
            file=SimpleUploadedFile('handout.pdf', b'%PDF-1.4\nhandout', content_type='application/pdf'),
        )
        self.narration = SlideNarration.objects.create(
            slide=self.content_slide, language='en', script_text='Hello there.',
            audio_file=SimpleUploadedFile('narration.mp3', b'fake audio bytes', content_type='audio/mpeg'),
        )

        self.quiz_slide = Slide.objects.create(lesson=self.lesson, order=2, slide_type=Slide.SlideType.QUIZ)
        quiz = Quiz.objects.create(slide=self.quiz_slide, title='Quiz', pass_percentage=60)
        self.question = Question.objects.create(
            quiz=quiz, question_text='Categorize this', order=1, question_type=Question.QuestionType.CATEGORIZE,
            image=make_test_image_upload('question.png', color='blue'),
        )
        bucket = CategoryBucket.objects.create(question=self.question, label='Bucket A', order=1)
        self.categorize_item = CategorizeItem.objects.create(
            question=self.question, item_text='Item 1', correct_bucket=bucket, order=1,
            item_image=make_test_image_upload('item.png', color='green'),
        )

        self.scenario_slide = Slide.objects.create(lesson=self.lesson, order=3, slide_type=Slide.SlideType.SCENARIO)
        self.scenario_node = ScenarioNode.objects.create(
            slide=self.scenario_slide, node_key='start', is_start=True,
            prompt_image=make_test_image_upload('node.png', color='yellow'),
        )

    def _clone(self):
        self.auth_as(self.platform_admin)
        response = self.client.post(f'/api/courses/{self.platform_course.slug}/clone/', {'organization': self.org.id})
        self.assertEqual(response.status_code, 201, response.data)
        return Course.objects.get(slug=response.data['slug'])

    def test_every_file_field_is_deep_copied_not_shared(self):
        cloned = self._clone()
        cloned_lesson = Lesson.objects.get(module__course=cloned)
        cloned_content_slide = Slide.objects.get(lesson=cloned_lesson, order=1)
        cloned_element = cloned_content_slide.elements.get()
        cloned_narration = SlideNarration.objects.get(slide=cloned_content_slide)
        cloned_question = Question.objects.get(quiz__slide__lesson=cloned_lesson)
        cloned_item = cloned_question.categorize_items.get()
        cloned_node = ScenarioNode.objects.get(slide__lesson=cloned_lesson, node_key='start')

        pairs = [
            ('cover_image', self.platform_course.cover_image, cloned.cover_image),
            ('content_file', self.lesson.content_file, cloned_lesson.content_file),
            ('element.video_file', self.element.video_file, cloned_element.video_file),
            ('element.file', self.element.file, cloned_element.file),
            ('narration.audio_file', self.narration.audio_file, cloned_narration.audio_file),
            ('question.image', self.question.image, cloned_question.image),
            ('categorize_item.item_image', self.categorize_item.item_image, cloned_item.item_image),
            ('scenario_node.prompt_image', self.scenario_node.prompt_image, cloned_node.prompt_image),
        ]
        for label, source_field, cloned_field in pairs:
            with self.subTest(field=label):
                self.assertTrue(cloned_field, f'{label} was not copied at all')
                self.assertNotEqual(
                    cloned_field.name, source_field.name,
                    f'{label} clone shares the exact same storage path as the source — not independent',
                )
                source_field.open('rb')
                cloned_field.open('rb')
                try:
                    self.assertEqual(
                        cloned_field.read(), source_field.read(), f'{label} clone content does not match the source'
                    )
                finally:
                    source_field.close()
                    cloned_field.close()

    def test_deleting_the_clones_file_does_not_touch_the_source(self):
        cloned = self._clone()
        cloned_lesson = Lesson.objects.get(module__course=cloned)
        cloned_element = Slide.objects.get(lesson=cloned_lesson, order=1).elements.get()

        cloned_element.video_file.delete(save=True)

        self.element.refresh_from_db()
        self.assertTrue(self.element.video_file)
        self.element.video_file.open('rb')
        try:
            self.assertEqual(self.element.video_file.read(), b'fake video bytes')
        finally:
            self.element.video_file.close()

    def test_deleting_the_sources_file_does_not_touch_the_clone(self):
        cloned = self._clone()
        cloned_lesson = Lesson.objects.get(module__course=cloned)
        cloned_element = Slide.objects.get(lesson=cloned_lesson, order=1).elements.get()

        self.element.video_file.delete(save=True)

        cloned_element.refresh_from_db()
        self.assertTrue(cloned_element.video_file)
        cloned_element.video_file.open('rb')
        try:
            self.assertEqual(cloned_element.video_file.read(), b'fake video bytes')
        finally:
            cloned_element.video_file.close()

    def test_copy_lesson_backfill_also_deep_copies_files(self):
        from courses.services import copy_lesson

        target_course = Course.objects.create(
            title='Target', slug='clone-target', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION,
        )
        target_module = Module.objects.create(course=target_course, title='Module 1', order=1)

        copied = copy_lesson(self.lesson, target_module)
        copied_slide = Slide.objects.get(lesson=copied, order=1)
        copied_element = copied_slide.elements.get()

        self.assertNotEqual(copied_element.video_file.name, self.element.video_file.name)
        copied_element.video_file.delete(save=True)

        self.element.refresh_from_db()
        self.assertTrue(self.element.video_file)


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


class SlideOrderingTests(BaseAPITestCase):
    """Slide.order is server-authoritative: created at the end of the lesson,
    kept contiguous 1..N on delete — a gapped sequence (e.g. from a cloned
    course with its first slides deleted) must never block adding a slide."""

    def setUp(self):
        super().setUp()
        # lesson2 starts empty; give it a gapped order sequence like a clone
        # that had slides 1-3 deleted would have.
        self.s6 = Slide.objects.create(lesson=self.lesson2, order=6, slide_type=Slide.SlideType.CONTENT)
        self.s7 = Slide.objects.create(lesson=self.lesson2, order=7, slide_type=Slide.SlideType.CONTENT)
        self.s8 = Slide.objects.create(lesson=self.lesson2, order=8, slide_type=Slide.SlideType.CONTENT)

    def test_new_slide_appends_past_the_highest_order_not_the_count(self):
        self.auth_as(self.org_admin)
        response = self.client.post('/api/slides/', {
            'lesson': self.lesson2.id, 'title': 'Added', 'slide_type': 'CONTENT',
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['order'], 9)

    def test_client_supplied_order_is_ignored(self):
        self.auth_as(self.org_admin)
        response = self.client.post('/api/slides/', {
            'lesson': self.lesson2.id, 'slide_type': 'CONTENT', 'order': 6,
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['order'], 9)

    def test_first_slide_in_an_empty_lesson_gets_order_1(self):
        empty_lesson = Lesson.objects.create(module=self.module, title='Empty', order=3, estimated_minutes=5)
        self.auth_as(self.org_admin)
        response = self.client.post('/api/slides/', {'lesson': empty_lesson.id, 'slide_type': 'CONTENT'})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['order'], 1)

    def test_deleting_a_slide_renumbers_the_rest_to_be_contiguous(self):
        self.auth_as(self.org_admin)
        response = self.client.delete(f'/api/slides/{self.s7.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            list(Slide.objects.filter(lesson=self.lesson2).order_by('order').values_list('id', 'order')),
            [(self.s6.id, 1), (self.s8.id, 2)],
        )

    def test_duplicate_places_the_copy_at_the_end(self):
        self.auth_as(self.org_admin)
        response = self.client.post(f'/api/slides/{self.s6.id}/duplicate/')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['order'], 9)


class ModuleLessonOrderingTests(BaseAPITestCase):
    """Module.order (per course) and Lesson.order (per module) are
    server-authoritative in exactly the same way as Slide.order — a gapped
    sequence from a cloned course with its first modules/lessons deleted must
    not block adding one, and a delete renumbers the rest to 1..N."""

    def setUp(self):
        super().setUp()
        # published_org_course already has self.module at order 1. Add a gap
        # like deleting modules 2-5 of a clone would leave.
        self.mod_a = Module.objects.create(course=self.published_org_course, title='A', order=6)
        self.mod_b = Module.objects.create(course=self.published_org_course, title='B', order=7)
        # self.module already has lesson1 (order 1) and lesson2 (order 2); give
        # mod_a a gapped lesson sequence.
        self.les_x = Lesson.objects.create(module=self.mod_a, title='X', order=6, estimated_minutes=1)
        self.les_y = Lesson.objects.create(module=self.mod_a, title='Y', order=7, estimated_minutes=1)
        self.les_z = Lesson.objects.create(module=self.mod_a, title='Z', order=8, estimated_minutes=1)

    def test_new_module_appends_past_the_highest_order(self):
        self.auth_as(self.org_admin)
        response = self.client.post('/api/modules/', {
            'course': self.published_org_course.id, 'title': 'New', 'order': 6,
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['order'], 8)

    def test_deleting_a_module_renumbers_the_rest(self):
        self.auth_as(self.org_admin)
        response = self.client.delete(f'/api/modules/{self.mod_a.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            list(Module.objects.filter(course=self.published_org_course).order_by('order').values_list('id', 'order')),
            [(self.module.id, 1), (self.mod_b.id, 2)],
        )

    def test_new_lesson_appends_past_the_highest_order_in_its_module(self):
        self.auth_as(self.org_admin)
        response = self.client.post('/api/lessons/', {
            'module': self.mod_a.id, 'title': 'New', 'lesson_type': 'TEXT', 'order': 6,
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['order'], 9)

    def test_deleting_a_lesson_renumbers_the_rest_of_its_module(self):
        self.auth_as(self.org_admin)
        response = self.client.delete(f'/api/lessons/{self.les_y.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            list(Lesson.objects.filter(module=self.mod_a).order_by('order').values_list('id', 'order')),
            [(self.les_x.id, 1), (self.les_z.id, 2)],
        )


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


def make_quiz_course(*, title, slug, organization, path_order, minimum_assessment_level=None, pass_percentage=70):
    """A published, path_order'd course with a single one-question quiz —
    enough to drive both completion and a quiz-average score for the Staff
    Training Report tests below. Returns (course, quiz)."""
    course = Course.objects.create(
        title=title, slug=slug, organization=organization,
        content_owner=Course.ContentOwner.ORGANIZATION, is_published=True,
        path_order=path_order, minimum_assessment_level=minimum_assessment_level,
    )
    module = Module.objects.create(course=course, title='Module 1', order=1)
    lesson = Lesson.objects.create(module=module, title='Lesson 1', order=1, estimated_minutes=5)
    slide = Slide.objects.create(lesson=lesson, order=1, title='Quiz', slide_type=Slide.SlideType.QUIZ)
    quiz = Quiz.objects.create(slide=slide, title=f'{title} Quiz', pass_percentage=pass_percentage, max_attempts=5)
    question = Question.objects.create(quiz=quiz, question_text='Q?', order=1, points=1)
    Choice.objects.create(question=question, choice_text='Correct', is_correct=True)
    Choice.objects.create(question=question, choice_text='Wrong', is_correct=False)
    return course, quiz


def complete_course(user, course, *, completed_at):
    Enrollment.objects.update_or_create(
        user=user, course=course,
        defaults={'status': Enrollment.Status.COMPLETED, 'completed_at': completed_at, 'progress_percent': 100},
    )


def submit_quiz_attempt(user, quiz, *, attempt_number, score_percent, submitted_at):
    QuizAttempt.objects.create(
        user=user, quiz=quiz, attempt_number=attempt_number,
        submitted_at=submitted_at, score_percent=score_percent, passed=score_percent >= quiz.pass_percentage,
    )


def submit_level_attempt(user, assessment_level, *, score_percent, passed, submitted_at):
    LevelAssessmentAttempt.objects.create(
        user=user, assessment_level=assessment_level, submitted_at=submitted_at,
        score_percent=score_percent, passed=passed,
    )


class StaffTrainingReportApiTests(BaseAPITestCase):
    """
    Covers accounts/courses/assessments/levelassessments data assembled into
    one report row per staff member — see courses.views._build_staff_training_report.
    """

    URL = '/api/reports/staff-training/'
    RANGE = {'date_from': '2026-01-01', 'date_to': '2026-01-31'}
    IN_RANGE = timezone.make_aware(datetime(2026, 1, 15, 9, 0))
    IN_RANGE_LATER = timezone.make_aware(datetime(2026, 1, 20, 9, 0))
    OUT_OF_RANGE = timezone.make_aware(datetime(2025, 6, 1, 9, 0))

    def setUp(self):
        super().setUp()
        OrganizationSettings.objects.filter(organization=self.org).update(pass_mark_percent=70)
        self.org.refresh_from_db()

        self.foundation_course, self.foundation_quiz = make_quiz_course(
            title='AML/CFT General Awareness Training', slug='aml-foundation', organization=self.org, path_order=1,
        )
        self.officer_course, self.officer_quiz = make_quiz_course(
            title='KYC/CDD', slug='kyc-cdd', organization=self.org, path_order=2,
            minimum_assessment_level=User.AssessmentLevel.OFFICER,
        )
        self.officer_level = configure_assessment_level(self.org, User.AssessmentLevel.OFFICER)
        self.front_line_level = configure_assessment_level(self.org, User.AssessmentLevel.ASSISTANT_SUPERVISOR)

        # A different organization's own curriculum course — must never leak
        # into self.org's report columns.
        Course.objects.create(
            title='Other Org Only Course', slug='other-org-only', organization=self.other_org,
            content_owner=Course.ContentOwner.ORGANIZATION, is_published=True, path_order=1,
        )

        def make_staff(email, **extra):
            return User.objects.create_user(
                email=email, password='pass12345', role=User.Role.LEARNER, organization=self.org, is_demo=False,
                **extra,
            )

        # Alice: passes everything, but needed a retake on the officer course
        # and on her level assessment — drives both "Total Course Retakes"
        # and the dynamic Attempt/Score column count (2, the report's max).
        self.alice = make_staff(
            'alice@acme.test', first_name='Alice', last_name='Amaya',
            assessment_level=User.AssessmentLevel.OFFICER,
        )
        complete_course(self.alice, self.foundation_course, completed_at=self.IN_RANGE)
        submit_quiz_attempt(self.alice, self.foundation_quiz, attempt_number=1, score_percent=90, submitted_at=self.IN_RANGE)
        submit_quiz_attempt(self.alice, self.officer_quiz, attempt_number=1, score_percent=50, submitted_at=self.IN_RANGE)
        submit_quiz_attempt(self.alice, self.officer_quiz, attempt_number=2, score_percent=85, submitted_at=self.IN_RANGE_LATER)
        complete_course(self.alice, self.officer_course, completed_at=self.IN_RANGE_LATER)
        submit_level_attempt(self.alice, self.officer_level, score_percent=40, passed=False, submitted_at=self.IN_RANGE)
        submit_level_attempt(self.alice, self.officer_level, score_percent=80, passed=True, submitted_at=self.IN_RANGE_LATER)

        # Bob: zero activity in the report window at all.
        self.bob = make_staff('bob@acme.test', first_name='Bob', last_name='Basnet', assessment_level=User.AssessmentLevel.OFFICER)

        # Carol: passes both path courses cleanly, but fails her one level
        # assessment attempt — Final Status must be Fail despite the course pass.
        self.carol = make_staff('carol@acme.test', first_name='Carol', last_name='Carki', assessment_level=User.AssessmentLevel.OFFICER)
        complete_course(self.carol, self.foundation_course, completed_at=self.IN_RANGE)
        submit_quiz_attempt(self.carol, self.foundation_quiz, attempt_number=1, score_percent=90, submitted_at=self.IN_RANGE)
        complete_course(self.carol, self.officer_course, completed_at=self.IN_RANGE)
        submit_quiz_attempt(self.carol, self.officer_quiz, attempt_number=1, score_percent=85, submitted_at=self.IN_RANGE)
        submit_level_attempt(self.carol, self.officer_level, score_percent=30, passed=False, submitted_at=self.IN_RANGE)

        # Dave: a different assessment level (Front-Line) — completes his one
        # path course (Foundation only; Officer is above his tier) but with a
        # failing average, while passing his level assessment — Final Status
        # must be Fail despite the level-assessment pass (the vice versa case).
        self.dave = make_staff(
            'dave@acme.test', first_name='Dave', last_name='Dahal',
            assessment_level=User.AssessmentLevel.ASSISTANT_SUPERVISOR,
        )
        complete_course(self.dave, self.foundation_course, completed_at=self.IN_RANGE)
        submit_quiz_attempt(self.dave, self.foundation_quiz, attempt_number=1, score_percent=40, submitted_at=self.IN_RANGE)
        submit_level_attempt(self.dave, self.front_line_level, score_percent=90, passed=True, submitted_at=self.IN_RANGE)

    def get_report(self, as_user, **params):
        self.auth_as(as_user)
        query = {**self.RANGE, **params}
        return self.client.get(self.URL, query)

    def row_for(self, headers, rows, email):
        email_index = headers.index('Email Address')
        for row in rows:
            if row[email_index] == email:
                return dict(zip(headers, row))
        return None

    def test_learner_and_instructor_forbidden(self):
        for user in (self.learner, self.instructor):
            self.assertEqual(self.get_report(user).status_code, 403)

    def test_platform_admin_must_select_an_organization(self):
        response = self.get_report(self.platform_admin)
        self.assertEqual(response.status_code, 400)

    def test_requires_a_date_range(self):
        self.auth_as(self.org_admin)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 400)

    def test_every_staff_member_appears_regardless_of_activity(self):
        response = self.get_report(self.org_admin)
        self.assertEqual(response.status_code, 200)
        headers, rows = response.data['headers'], response.data['rows']
        emails = [row[headers.index('Email Address')] for row in rows]
        # self.learner (BaseAPITestCase's own fixture) is itself a real staff
        # member of self.org, so it's expected alongside the four built here.
        self.assertEqual(
            set(emails), {self.alice.email, self.bob.email, self.carol.email, self.dave.email, self.learner.email}
        )

    def test_columns_only_include_this_organizations_curriculum(self):
        response = self.get_report(self.org_admin)
        headers = response.data['headers']
        self.assertIn('AML/CFT General Awareness Training', headers)
        self.assertIn('KYC/CDD', headers)
        self.assertNotIn('Other Org Only Course', headers)

    def test_attempt_score_columns_scale_to_the_actual_highest_attempt_count(self):
        response = self.get_report(self.org_admin)
        headers = response.data['headers']
        # Alice needed 2 level-assessment attempts — the report's max — so
        # every row gets exactly Attempt 1/Score 1/Attempt 2/Score 2, no more.
        self.assertIn('Attempt 1', headers)
        self.assertIn('Score 1', headers)
        self.assertIn('Attempt 2', headers)
        self.assertIn('Score 2', headers)
        self.assertNotIn('Attempt 3', headers)
        self.assertEqual(headers.index('Score 1'), headers.index('Attempt 1') + 1)
        self.assertEqual(headers.index('Attempt 2'), headers.index('Score 1') + 1)

    def test_zero_activity_staff_member_has_blank_cells_but_fails_overall(self):
        response = self.get_report(self.org_admin)
        headers, rows = response.data['headers'], response.data['rows']
        bob_row = self.row_for(headers, rows, self.bob.email)
        self.assertEqual(bob_row['Course Path Completed (Pass/Fail)'], '')
        self.assertEqual(bob_row['Date Path Completed'], '')
        self.assertEqual(bob_row['Total Course Retakes'], 0)
        self.assertEqual(bob_row['AML/CFT General Awareness Training'], '')
        self.assertEqual(bob_row['Level Assessment (Pass/Fail)'], '')
        self.assertEqual(bob_row['Final Status (Pass/Fail)'], 'Fail')

    def test_staff_with_retakes_reports_correct_totals_and_scores(self):
        response = self.get_report(self.org_admin)
        headers, rows = response.data['headers'], response.data['rows']
        alice_row = self.row_for(headers, rows, self.alice.email)
        self.assertEqual(alice_row['Total Course Retakes'], 1)
        self.assertEqual(alice_row['Course Path Completed (Pass/Fail)'], 'Pass')
        self.assertEqual(alice_row['Date Path Completed'], self.IN_RANGE_LATER.date().isoformat())
        self.assertEqual(alice_row['AML/CFT General Awareness Training'], 90.0)
        self.assertEqual(alice_row['KYC/CDD'], 85.0)
        self.assertEqual(alice_row['Attempt 1'], 'Fail')
        self.assertEqual(alice_row['Score 1'], 40.0)
        self.assertEqual(alice_row['Attempt 2'], 'Pass')
        self.assertEqual(alice_row['Score 2'], 80.0)
        self.assertEqual(alice_row['Level Assessment (Pass/Fail)'], 'Pass')
        self.assertEqual(alice_row['Final Status (Pass/Fail)'], 'Pass')

    def test_final_status_fails_when_courses_pass_but_level_assessment_fails(self):
        response = self.get_report(self.org_admin)
        headers, rows = response.data['headers'], response.data['rows']
        carol_row = self.row_for(headers, rows, self.carol.email)
        self.assertEqual(carol_row['Course Path Completed (Pass/Fail)'], 'Pass')
        self.assertEqual(carol_row['Level Assessment (Pass/Fail)'], 'Fail')
        self.assertEqual(carol_row['Final Status (Pass/Fail)'], 'Fail')

    def test_final_status_fails_when_level_assessment_passes_but_courses_fail(self):
        response = self.get_report(self.org_admin)
        headers, rows = response.data['headers'], response.data['rows']
        dave_row = self.row_for(headers, rows, self.dave.email)
        self.assertEqual(dave_row['Course Path Completed (Pass/Fail)'], 'Fail')
        self.assertEqual(dave_row['Level Assessment (Pass/Fail)'], 'Pass')
        self.assertEqual(dave_row['Final Status (Pass/Fail)'], 'Fail')
        # Dave's path is Foundation-only (Officer is above his tier) — the
        # Officer course column still exists (org-wide curriculum) but is blank.
        self.assertEqual(dave_row['KYC/CDD'], '')

    def test_activity_outside_the_date_range_is_excluded(self):
        complete_course(self.bob, self.foundation_course, completed_at=self.OUT_OF_RANGE)
        submit_quiz_attempt(self.bob, self.foundation_quiz, attempt_number=1, score_percent=95, submitted_at=self.OUT_OF_RANGE)

        response = self.get_report(self.org_admin)
        headers, rows = response.data['headers'], response.data['rows']
        bob_row = self.row_for(headers, rows, self.bob.email)
        self.assertEqual(bob_row['Course Path Completed (Pass/Fail)'], '')
        self.assertEqual(bob_row['AML/CFT General Awareness Training'], '')

    def test_org_admin_cannot_see_another_organizations_staff(self):
        response = self.get_report(self.org_admin)
        headers, rows = response.data['headers'], response.data['rows']
        emails = [row[headers.index('Email Address')] for row in rows]
        self.assertNotIn(self.other_org_learner.email, emails)

    def test_platform_admin_can_select_the_organization(self):
        response = self.get_report(self.platform_admin, organization=self.org.id)
        self.assertEqual(response.status_code, 200)
        headers, rows = response.data['headers'], response.data['rows']
        emails = [row[headers.index('Email Address')] for row in rows]
        self.assertIn(self.alice.email, emails)

    def test_csv_and_xlsx_exports_match_the_json_preview_exactly(self):
        json_response = self.get_report(self.org_admin)
        headers, rows = json_response.data['headers'], json_response.data['rows']

        csv_response = self.get_report(self.org_admin, export='csv')
        self.assertEqual(csv_response['Content-Type'], 'text/csv')
        csv_rows = list(csv.reader(io.StringIO(csv_response.content.decode())))
        self.assertEqual(csv_rows[0], headers)
        for expected, actual in zip(rows, csv_rows[1:]):
            expected_as_strings = ['' if cell == '' else str(cell) for cell in expected]
            self.assertEqual(actual, expected_as_strings)

        xlsx_response = self.get_report(self.org_admin, export='xlsx')
        self.assertEqual(
            xlsx_response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        workbook = load_workbook(io.BytesIO(xlsx_response.content))
        sheet = workbook.active
        xlsx_header_row = [cell.value for cell in sheet[1]]
        self.assertEqual(xlsx_header_row, headers)
        xlsx_data_rows = [list(row) for row in sheet.iter_rows(min_row=2, values_only=True)]
        for expected, actual in zip(rows, xlsx_data_rows):
            expected_as_xlsx = [None if cell == '' else cell for cell in expected]
            self.assertEqual(actual, expected_as_xlsx)

        self.assertTrue(sheet.cell(row=1, column=1).font.bold)
        self.assertEqual(sheet.freeze_panes, 'A2')

    def test_csv_export_neutralizes_formula_injection(self):
        evil = User.objects.create_user(
            email='formula-report@acme.test', password='pass12345', role=User.Role.LEARNER,
            organization=self.org, is_demo=False, first_name='=HYPERLINK("http://evil.test")', last_name='X',
        )
        response = self.get_report(self.org_admin, export='csv')
        content = response.content.decode()
        self.assertNotIn('\n=HYPERLINK', content)
        self.assertIn("'=HYPERLINK", content)


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

    def test_password_reset_request_is_rate_limited(self):
        payload = {'email': self.learner.email}
        statuses = [self.client.post('/api/auth/password-reset/', payload).status_code for _ in range(5)]
        self.assertTrue(all(code == 200 for code in statuses))

        throttled = self.client.post('/api/auth/password-reset/', payload)
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

    def test_learners_organization_template_used_when_no_course_override_exists(self):
        make_test_certificate_template(name='Acme template', organization=self.org)

        certificate = generate_certificate(self.learner, self.published_org_course)

        self.assertEqual(certificate.pdf_file.read()[:4], b'%PDF')
        # Confirms the org template — not the seeded platform default — was
        # actually the one resolved, not just that *a* PDF rendered.
        self.assertEqual(_resolve_template(self.published_org_course, self.learner).organization_id, self.org.id)

    def test_course_override_still_wins_over_the_learners_organization_template(self):
        make_test_certificate_template(name='Acme template', organization=self.org)
        course_template = make_test_certificate_template(name='Course-specific template')
        self.published_org_course.certificate_template = course_template
        self.published_org_course.save()

        resolved = _resolve_template(self.published_org_course, self.learner)
        self.assertEqual(resolved.id, course_template.id)

    def test_platform_default_used_when_learner_has_no_organization(self):
        self.learner.organization = None
        self.learner.save()

        resolved = _resolve_template(self.published_org_course, self.learner)
        self.assertTrue(resolved.is_default)

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

    def test_instructor_cannot_see_the_platform_default_template(self):
        # Org-scoped now: the platform-level template is a platform-wide
        # branding asset, not an individual organization's to see or manage.
        self.auth_as(self.instructor)
        response = self.client.get('/api/certificate-templates/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_instructor_sees_and_can_update_only_their_own_organizations_template(self):
        own_template = make_test_certificate_template(name='Acme template', organization=self.org)
        make_test_certificate_template(name='Other Bank template', organization=self.other_org)

        self.auth_as(self.instructor)
        listing = self.client.get('/api/certificate-templates/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([t['id'] for t in listing.data], [own_template.id])

        response = self.client.patch(
            f'/api/certificate-templates/{own_template.id}/',
            {'staff_name_x_percent': 42.5, 'staff_name_text_align': 'LEFT'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        own_template.refresh_from_db()
        self.assertEqual(own_template.staff_name_x_percent, 42.5)

    def test_instructor_cannot_access_another_organizations_template(self):
        other_template = make_test_certificate_template(name='Other Bank template', organization=self.other_org)
        self.auth_as(self.instructor)
        response = self.client.get(f'/api/certificate-templates/{other_template.id}/')
        self.assertEqual(response.status_code, 404)

    def test_platform_admin_sees_every_organizations_template_and_the_platform_default(self):
        make_test_certificate_template(name='Acme template', organization=self.org)
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/certificate-templates/')
        self.assertEqual(response.status_code, 200)
        # The seeded platform default (organization=None) plus the one just created.
        self.assertEqual(len(response.data), 2)

    def test_instructor_can_create_a_template_for_their_own_organization(self):
        image_buffer = io.BytesIO()
        Image.new('RGB', (400, 300), color='white').save(image_buffer, format='PNG')
        self.auth_as(self.instructor)
        response = self.client.post(
            '/api/certificate-templates/',
            {
                'name': 'Acme certificate',
                'organization': self.org.id,
                'background_image': SimpleUploadedFile('bg.png', image_buffer.getvalue(), content_type='image/png'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['organization'], self.org.id)
        self.assertFalse(response.data['is_default'])

    def test_instructor_cannot_create_a_template_for_a_different_organization(self):
        image_buffer = io.BytesIO()
        Image.new('RGB', (400, 300), color='white').save(image_buffer, format='PNG')
        self.auth_as(self.instructor)
        response = self.client.post(
            '/api/certificate-templates/',
            {
                'name': 'Sneaky',
                'organization': self.other_org.id,
                'background_image': SimpleUploadedFile('bg.png', image_buffer.getvalue(), content_type='image/png'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    def test_instructor_cannot_create_the_platform_default_template(self):
        image_buffer = io.BytesIO()
        Image.new('RGB', (400, 300), color='white').save(image_buffer, format='PNG')
        self.auth_as(self.instructor)
        response = self.client.post(
            '/api/certificate-templates/',
            {'name': 'Sneaky platform template', 'background_image': SimpleUploadedFile('bg.png', image_buffer.getvalue(), content_type='image/png')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_mark_an_organization_scoped_template_as_default(self):
        image_buffer = io.BytesIO()
        Image.new('RGB', (400, 300), color='white').save(image_buffer, format='PNG')
        self.auth_as(self.platform_admin)
        response = self.client.post(
            '/api/certificate-templates/',
            {
                'name': 'Bad combo',
                'organization': self.org.id,
                'is_default': True,
                'background_image': SimpleUploadedFile('bg.png', image_buffer.getvalue(), content_type='image/png'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('is_default', response.data)

    def test_only_one_template_allowed_per_organization(self):
        make_test_certificate_template(name='First', organization=self.org)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_test_certificate_template(name='Second', organization=self.org)

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

    def test_bulk_upload_extended_columns_captures_titles_and_assessment_level(self):
        csv_content = (
            'Name,Email,Corporate Title,Functional Title,Branch/Department,Assessment Level,Organization\n'
            f'Alice Alpha,alice@example.com,VP,Compliance Analyst,Head Office,Officer,{self.org.name}\n'
            f'Bob Beta,bob@example.com,SVP,Risk Lead,Branch Office,Senior Management,{self.org.name}\n'
        )
        upload = SimpleUploadedFile('demo_users.csv', csv_content.encode('utf-8'), content_type='text/csv')

        self.auth_as(self.instructor)
        response = self.client.post('/api/demo-users/bulk/', {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], ['alice@example.com', 'bob@example.com'])

        alice = User.objects.get(email='alice@example.com')
        self.assertEqual(alice.corporate_title, 'VP')
        self.assertEqual(alice.functional_title, 'Compliance Analyst')
        self.assertEqual(alice.branch_department, 'Head Office')
        self.assertEqual(alice.assessment_level, 'officer')

        bob = User.objects.get(email='bob@example.com')
        self.assertEqual(bob.assessment_level, 'senior_management')

    def test_bulk_upload_extended_columns_rejects_invalid_assessment_level(self):
        csv_content = (
            'Name,Email,Corporate Title,Functional Title,Branch/Department,Assessment Level,Organization\n'
            f'Alice Alpha,alice@example.com,VP,Compliance Analyst,Head Office,Director,{self.org.name}\n'
        )
        upload = SimpleUploadedFile('demo_users.csv', csv_content.encode('utf-8'), content_type='text/csv')

        self.auth_as(self.instructor)
        response = self.client.post('/api/demo-users/bulk/', {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], [])
        self.assertEqual(len(response.data['failed']), 1)
        self.assertIn('Invalid Assessment Level', response.data['failed'][0]['reason'])
        self.assertFalse(User.objects.filter(email='alice@example.com').exists())

    def test_bulk_upload_extended_columns_rejects_missing_assessment_level(self):
        csv_content = (
            'Name,Email,Corporate Title,Functional Title,Branch/Department,Assessment Level,Organization\n'
            f'Alice Alpha,alice@example.com,VP,Compliance Analyst,Head Office,,{self.org.name}\n'
        )
        upload = SimpleUploadedFile('demo_users.csv', csv_content.encode('utf-8'), content_type='text/csv')

        self.auth_as(self.instructor)
        response = self.client.post('/api/demo-users/bulk/', {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], [])
        self.assertEqual(len(response.data['failed']), 1)
        self.assertIn('Invalid Assessment Level', response.data['failed'][0]['reason'])

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


class PasswordResetApiTests(BaseAPITestCase):
    GENERIC_DETAIL = "If an account exists for that email, we've sent a password reset link."

    def setUp(self):
        super().setUp()
        cache.clear()  # isolate the password-reset throttle counter used by these endpoints

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _valid_uid_token(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uid, token

    def test_request_sends_email_and_generic_response_for_existing_user(self):
        response = self.client.post('/api/auth/password-reset/', {'email': self.learner.email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], self.GENERIC_DETAIL)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.learner.email, mail.outbox[0].to)
        self.assertIn('/reset-password/', mail.outbox[0].body)

    def test_request_is_case_insensitive_on_email(self):
        response = self.client.post('/api/auth/password-reset/', {'email': self.learner.email.upper()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_request_returns_generic_response_and_no_email_for_unknown_address(self):
        response = self.client.post('/api/auth/password-reset/', {'email': 'nobody@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], self.GENERIC_DETAIL)
        self.assertEqual(len(mail.outbox), 0)

    def test_request_returns_generic_response_and_no_email_for_inactive_user(self):
        self.learner.is_active = False
        self.learner.save(update_fields=['is_active'])

        response = self.client.post('/api/auth/password-reset/', {'email': self.learner.email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], self.GENERIC_DETAIL)
        self.assertEqual(len(mail.outbox), 0)

    def test_request_still_returns_generic_response_when_email_send_fails(self):
        # An SMTP outage on a real account must not 500 — that would turn
        # this endpoint into an account-existence oracle (only existing
        # accounts reach the send call at all).
        with patch('accounts.views.send_password_reset_email', side_effect=Exception('smtp down')):
            response = self.client.post('/api/auth/password-reset/', {'email': self.learner.email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], self.GENERIC_DETAIL)

    def test_confirm_with_valid_token_resets_password_and_clears_must_reset_flag(self):
        self.learner.must_reset_password = True
        self.learner.save(update_fields=['must_reset_password'])
        uid, token = self._valid_uid_token(self.learner)

        response = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': uid, 'token': token, 'new_password': 'BrandNewPassw0rd1',
        })
        self.assertEqual(response.status_code, 200)

        self.learner.refresh_from_db()
        self.assertTrue(self.learner.check_password('BrandNewPassw0rd1'))
        self.assertFalse(self.learner.must_reset_password)

        login = self.client.post('/api/auth/login/', {
            'email': self.learner.email, 'password': 'BrandNewPassw0rd1',
        })
        self.assertEqual(login.status_code, 200)

    def test_confirm_with_invalid_token_returns_400_and_leaves_password_unchanged(self):
        uid, _ = self._valid_uid_token(self.learner)
        response = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': uid, 'token': 'not-a-real-token', 'new_password': 'BrandNewPassw0rd1',
        })
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.learner.check_password('pass12345'))

    def test_confirm_with_invalid_uid_returns_400(self):
        _, token = self._valid_uid_token(self.learner)
        response = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': 'not-a-real-uid', 'token': token, 'new_password': 'BrandNewPassw0rd1',
        })
        self.assertEqual(response.status_code, 400)

    def test_confirm_token_cannot_be_reused_after_password_already_changed(self):
        uid, token = self._valid_uid_token(self.learner)
        first = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': uid, 'token': token, 'new_password': 'BrandNewPassw0rd1',
        })
        self.assertEqual(first.status_code, 200)

        second = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': uid, 'token': token, 'new_password': 'AnotherPassw0rd2',
        })
        self.assertEqual(second.status_code, 400)
        self.learner.refresh_from_db()
        self.assertTrue(self.learner.check_password('BrandNewPassw0rd1'))

    def test_confirm_rejects_password_failing_validators(self):
        uid, token = self._valid_uid_token(self.learner)
        response = self.client.post('/api/auth/password-reset-confirm/', {
            'uid': uid, 'token': token, 'new_password': '12345678',
        })
        self.assertEqual(response.status_code, 400)
        self.learner.refresh_from_db()
        self.assertTrue(self.learner.check_password('pass12345'))


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


class SlideNarrationFlowTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.content_slide = Slide.objects.create(
            lesson=self.lesson1, order=1, title='Intro Slide', slide_type=Slide.SlideType.CONTENT,
        )
        Element.objects.create(
            slide=self.content_slide, order=1, element_type=Element.ElementType.TEXT,
            rich_text='<p>Welcome to your AML training.</p>',
        )
        self.empty_slide = Slide.objects.create(
            lesson=self.lesson1, order=2, title='Empty Slide', slide_type=Slide.SlideType.CONTENT,
        )

    def test_learner_cannot_generate_narration(self):
        self.auth_as(self.learner)
        response = self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'en'})
        self.assertEqual(response.status_code, 403)

    def test_instructor_and_org_admin_cannot_generate_narration(self):
        for user in (self.instructor, self.org_admin):
            self.auth_as(user)
            response = self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'en'})
            self.assertEqual(response.status_code, 403)

    def test_generate_rejects_invalid_language(self):
        self.auth_as(self.platform_admin)
        response = self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'fr'})
        self.assertEqual(response.status_code, 400)

    def test_generate_fails_when_slide_has_no_narratable_text(self):
        self.auth_as(self.platform_admin)
        response = self.client.post('/api/slide-narrations/generate/', {'slide': self.empty_slide.id, 'language': 'en'})
        self.assertEqual(response.status_code, 400)

    @patch('narration.services._synthesize_speech')
    @patch('narration.services._generate_script')
    def test_platform_admin_can_generate_narration(self, mock_generate_script, mock_synthesize_speech):
        mock_generate_script.return_value = 'Welcome to this training module.'
        mock_synthesize_speech.return_value = (b'fake-mp3-bytes', 'en-US-JennyNeural')

        self.auth_as(self.platform_admin)
        response = self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'en'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['script_text'], 'Welcome to this training module.')
        self.assertEqual(response.data['voice_name'], 'en-US-JennyNeural')
        self.assertIsNotNone(response.data['audio_file'])

        narration = SlideNarration.objects.get(slide=self.content_slide, language='en')
        self.assertEqual(narration.generated_by, self.platform_admin)

    @patch('narration.services._synthesize_speech')
    @patch('narration.services._generate_script')
    def test_regenerating_one_language_leaves_the_other_untouched(self, mock_generate_script, mock_synthesize_speech):
        mock_generate_script.side_effect = ['English v1', 'Nepali script', 'English v2']
        mock_synthesize_speech.side_effect = [
            (b'audio-en-1', 'en-US-JennyNeural'),
            (b'audio-ne', 'ne-NP-HemkalaNeural'),
            (b'audio-en-2', 'en-US-JennyNeural'),
        ]
        self.auth_as(self.platform_admin)

        self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'en'})
        self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'ne'})
        self.assertEqual(SlideNarration.objects.filter(slide=self.content_slide).count(), 2)

        response = self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'en'})
        self.assertEqual(response.data['script_text'], 'English v2')
        self.assertEqual(SlideNarration.objects.filter(slide=self.content_slide).count(), 2)

        ne_narration = SlideNarration.objects.get(slide=self.content_slide, language='ne')
        self.assertEqual(ne_narration.script_text, 'Nepali script')

    @patch('narration.services._synthesize_speech')
    @patch('narration.services._generate_script')
    def test_learner_can_view_generated_narration_for_a_visible_course(self, mock_generate_script, mock_synthesize_speech):
        mock_generate_script.return_value = 'Script text'
        mock_synthesize_speech.return_value = (b'audio-bytes', 'en-US-JennyNeural')
        self.auth_as(self.platform_admin)
        self.client.post('/api/slide-narrations/generate/', {'slide': self.content_slide.id, 'language': 'en'})

        self.auth_as(self.learner)
        response = self.client.get(f'/api/slide-narrations/?slide={self.content_slide.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['language'], 'en')

    def test_learner_in_other_org_cannot_see_narration_for_a_course_they_cannot_view(self):
        self.auth_as(self.other_org_learner)
        response = self.client.get(f'/api/slide-narrations/?slide={self.content_slide.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)


class UserPreferenceApiTests(BaseAPITestCase):
    def test_learner_can_set_preferred_narration_language(self):
        self.auth_as(self.learner)
        self.assertEqual(self.client.get('/api/auth/me/').data['preferred_narration_language'], 'en')

        response = self.client.patch('/api/auth/me/', {'preferred_narration_language': 'ne'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['preferred_narration_language'], 'ne')

        self.learner.refresh_from_db()
        self.assertEqual(self.learner.preferred_narration_language, 'ne')

    def test_patch_me_cannot_change_role(self):
        self.auth_as(self.learner)
        response = self.client.patch('/api/auth/me/', {'preferred_narration_language': 'ne', 'role': 'PLATFORM_ADMIN'})
        self.assertEqual(response.status_code, 200)

        self.learner.refresh_from_db()
        self.assertEqual(self.learner.role, User.Role.LEARNER)


class LevelAssessmentAttemptServiceTests(TestCase):
    """
    Model + service coverage for the standalone role-based assessment system
    (independent of Course/Slide) — no API surface yet, so these exercise
    start_level_assessment_attempt directly, mirroring
    DemoUserProvisioningServiceTests' pattern for a service with no endpoint.
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Acme Bank', slug='acme-bank-level')
        self.user = User.objects.create_user(email='learner@example.com', password='pw', role=User.Role.LEARNER)
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=70, questions_per_attempt=3,
        )
        self.set_a = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        self.set_b = QuestionSet.objects.create(assessment_level=self.level, label='Set 2')
        # Questions spread across both sets — the draw pools them together.
        for question_set in (self.set_a, self.set_b):
            for i in range(2):
                question = LevelQuestion.objects.create(
                    question_set=question_set,
                    question_text=f'Question {question_set.label}-{i}',
                    question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
                )
                LevelChoice.objects.create(question=question, choice_text='Correct', is_correct=True)
                LevelChoice.objects.create(question=question, choice_text='Wrong', is_correct=False)

    def test_draws_the_configured_number_of_questions_from_the_combined_pool(self):
        attempt = start_level_assessment_attempt(user=self.user, assessment_level=self.level)

        self.assertEqual(len(attempt.questions_drawn), 3)
        pool_ids = set(LevelQuestion.objects.filter(question_set__assessment_level=self.level).values_list('id', flat=True))
        self.assertTrue(set(attempt.questions_drawn).issubset(pool_ids))
        self.assertEqual(len(set(attempt.questions_drawn)), 3)  # no duplicates

    def test_draw_never_includes_duplicate_visible_question_text(self):
        duplicate = LevelQuestion.objects.create(
            question_set=self.set_b,
            question_text='<p>  QUESTION set 1-0!!! </p>',
            question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
        )
        LevelChoice.objects.create(question=duplicate, choice_text='Correct', is_correct=True)
        LevelChoice.objects.create(question=duplicate, choice_text='Wrong', is_correct=False)

        attempt = start_level_assessment_attempt(user=self.user, assessment_level=self.level)
        drawn_texts = LevelQuestion.objects.filter(id__in=attempt.questions_drawn).values_list(
            'question_text', flat=True
        )
        normalized_texts = [normalize_question_text(text) for text in drawn_texts]

        self.assertEqual(len(normalized_texts), 3)
        self.assertEqual(len(set(normalized_texts)), 3)

    def test_rejects_when_rows_are_plentiful_but_unique_questions_are_insufficient(self):
        LevelQuestion.objects.filter(question_set__assessment_level=self.level).delete()
        OrganizationSettings.objects.filter(organization=self.org).update(questions_per_attempt=2)
        for text in ('What is AML?', ' what is aml ', '<strong>WHAT IS AML!!!</strong>'):
            question = LevelQuestion.objects.create(
                question_set=self.set_a,
                question_text=text,
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            )
            LevelChoice.objects.create(question=question, choice_text='Correct', is_correct=True)
            LevelChoice.objects.create(question=question, choice_text='Wrong', is_correct=False)

        with self.assertRaisesMessage(LevelAssessmentError, 'Not enough unique questions in the pool'):
            start_level_assessment_attempt(user=self.user, assessment_level=self.level)

        self.assertEqual(LevelAssessmentAttempt.objects.count(), 0)

    def test_second_attempt_blocked_while_one_is_in_progress(self):
        start_level_assessment_attempt(user=self.user, assessment_level=self.level)

        with self.assertRaises(LevelAssessmentError):
            start_level_assessment_attempt(user=self.user, assessment_level=self.level)

        self.assertEqual(LevelAssessmentAttempt.objects.filter(user=self.user, assessment_level=self.level).count(), 1)

    def test_retake_allowed_after_prior_attempt_is_submitted(self):
        first = start_level_assessment_attempt(user=self.user, assessment_level=self.level)
        first.submitted_at = timezone.now()
        first.score_percent = Decimal('33.33')
        first.passed = False
        first.save()

        second = start_level_assessment_attempt(user=self.user, assessment_level=self.level)

        self.assertNotEqual(first.id, second.id)
        self.assertEqual(LevelAssessmentAttempt.objects.filter(user=self.user, assessment_level=self.level).count(), 2)

    def test_retries_do_not_repeat_questions_until_the_pool_cycle_is_exhausted(self):
        # Nine unique questions at three per attempt support three completely
        # disjoint attempts. The fourth starts a new cycle instead of failing.
        for i in range(5):
            question = LevelQuestion.objects.create(
                question_set=self.set_a,
                question_text=f'Additional unique question {i}',
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            )
            LevelChoice.objects.create(question=question, choice_text='Correct', is_correct=True)
            LevelChoice.objects.create(question=question, choice_text='Wrong', is_correct=False)

        cycle_draws = []
        for _ in range(3):
            attempt = start_level_assessment_attempt(user=self.user, assessment_level=self.level)
            cycle_draws.append(set(attempt.questions_drawn))
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['submitted_at'])

        self.assertTrue(cycle_draws[0].isdisjoint(cycle_draws[1]))
        self.assertTrue(cycle_draws[0].isdisjoint(cycle_draws[2]))
        self.assertTrue(cycle_draws[1].isdisjoint(cycle_draws[2]))
        self.assertEqual(len(set().union(*cycle_draws)), 9)

        fourth = start_level_assessment_attempt(user=self.user, assessment_level=self.level)
        self.assertEqual(len(fourth.questions_drawn), 3)
        self.assertTrue(set(fourth.questions_drawn).issubset(set().union(*cycle_draws)))

    def test_no_repeat_cycle_uses_normalized_text_not_only_database_ids(self):
        # Six unique visible questions support two disjoint attempts. A
        # duplicate row with different markup/case must not sneak the first
        # attempt's wording into the second under a different database id.
        for i in range(2):
            question = LevelQuestion.objects.create(
                question_set=self.set_a,
                question_text=f'Additional normalized question {i}',
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            )
            LevelChoice.objects.create(question=question, choice_text='Correct', is_correct=True)
            LevelChoice.objects.create(question=question, choice_text='Wrong', is_correct=False)
        duplicate = LevelQuestion.objects.create(
            question_set=self.set_b,
            question_text='<p> QUESTION SET 1-0!!! </p>',
            question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
        )
        LevelChoice.objects.create(question=duplicate, choice_text='Correct', is_correct=True)
        LevelChoice.objects.create(question=duplicate, choice_text='Wrong', is_correct=False)

        first = start_level_assessment_attempt(user=self.user, assessment_level=self.level)
        first.submitted_at = timezone.now()
        first.save(update_fields=['submitted_at'])
        second = start_level_assessment_attempt(user=self.user, assessment_level=self.level)

        texts_by_id = dict(LevelQuestion.objects.filter(
            id__in=first.questions_drawn + second.questions_drawn
        ).values_list('id', 'question_text'))
        first_keys = {normalize_question_text(texts_by_id[question_id]) for question_id in first.questions_drawn}
        second_keys = {normalize_question_text(texts_by_id[question_id]) for question_id in second.questions_drawn}
        self.assertTrue(first_keys.isdisjoint(second_keys))

    def test_rejects_when_pool_smaller_than_questions_per_attempt(self):
        OrganizationSettings.objects.filter(organization=self.org).update(questions_per_attempt=999)

        with self.assertRaises(LevelAssessmentError):
            start_level_assessment_attempt(user=self.user, assessment_level=self.level)

        self.assertEqual(LevelAssessmentAttempt.objects.count(), 0)

    def test_different_users_may_each_have_their_own_open_attempt(self):
        other_user = User.objects.create_user(email='other@example.com', password='pw', role=User.Role.LEARNER)

        start_level_assessment_attempt(user=self.user, assessment_level=self.level)
        other_attempt = start_level_assessment_attempt(user=other_user, assessment_level=self.level)

        self.assertIsNotNone(other_attempt.id)


class LevelQuestionImportApiTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, questions_per_attempt=2,
        )
        self.other_org_level = configure_assessment_level(
            self.other_org, User.AssessmentLevel.OFFICER, questions_per_attempt=2,
        )

    def import_url(self, level):
        return f'/api/assessment-levels/{level.id}/import-questions/'

    def test_learner_cannot_import(self):
        upload = make_question_template_upload({'Set 1': []})
        self.auth_as(self.learner)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 403)

    def test_org_admin_cannot_import_into_another_organizations_level(self):
        upload = make_question_template_upload({'Set 1': []})
        self.auth_as(self.org_admin)
        response = self.client.post(self.import_url(self.other_org_level), {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 404)

    def test_valid_single_choice_and_multiple_answer_rows_are_created(self):
        rows = [
            ('Set 1', 'Capital of France?', 'Single Choice', 'Paris', 'Rome', 'Berlin', 'Madrid', '',
             'A', 2, 'Paris is correct.', 'Well done', 'Try again'),
            ('Set 1', 'Which are primary colors?', 'Multiple Answer', 'Red', 'Green', 'Blue', 'Purple', 'Yellow',
             'A, C', 1, '', '', ''),
        ]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['created']), 2)
        self.assertEqual(response.data['failed'], [])

        question_set = QuestionSet.objects.get(assessment_level=self.level, label='Set 1')
        self.assertEqual(question_set.questions.count(), 2)

        single_choice = question_set.questions.get(question_type=LevelQuestion.QuestionType.SINGLE_CHOICE)
        self.assertEqual(single_choice.marks, 2)
        self.assertEqual(single_choice.choices.count(), 4)  # Option E left blank
        self.assertEqual(single_choice.choices.get(is_correct=True).choice_text, 'Paris')

        multiple_answer = question_set.questions.get(question_type=LevelQuestion.QuestionType.MULTIPLE_ANSWER)
        self.assertEqual(multiple_answer.choices.count(), 5)
        self.assertEqual(
            set(multiple_answer.choices.filter(is_correct=True).values_list('choice_text', flat=True)),
            {'Red', 'Blue'},
        )

    def test_reuses_existing_question_set_by_label(self):
        existing_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        rows = [
            ('Set 1', 'Q1?', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', ''),
        ]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuestionSet.objects.filter(assessment_level=self.level, label='Set 1').count(), 1)
        self.assertEqual(existing_set.questions.count(), 1)

    def test_missing_options_and_bad_question_type_are_reported_not_dropped(self):
        rows = [
            # Missing Option D
            ('Set 1', 'Bad row 1', 'Single Choice', 'A', 'B', 'C', '', '', 'A', 1, '', '', ''),
            # Invalid Question Type
            ('Set 1', 'Bad row 2', 'Essay', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', ''),
            # Valid row in between — must still be created despite the failures around it
            ('Set 1', 'Good row', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', ''),
        ]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['created']), 1)
        self.assertEqual(len(response.data['failed']), 2)
        self.assertIn('Option D', response.data['failed'][0]['reason'])
        self.assertIn('Single Choice', response.data['failed'][1]['reason'])
        self.assertEqual(response.data['failed'][0]['row'], 2)
        self.assertEqual(response.data['failed'][1]['row'], 3)

    def test_correct_answer_referencing_empty_option_is_rejected(self):
        rows = [
            ('Set 1', 'Bad row', 'Single Choice', 'A', 'B', 'C', 'D', '', 'E', 1, '', '', ''),
        ]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], [])
        self.assertIn('empty option', response.data['failed'][0]['reason'])

    def test_single_choice_with_multiple_correct_answers_is_rejected(self):
        rows = [
            ('Set 1', 'Bad row', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A,B', 1, '', '', ''),
        ]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], [])
        self.assertIn('exactly one', response.data['failed'][0]['reason'])

    def test_non_positive_marks_is_rejected(self):
        rows = [
            ('Set 1', 'Bad row', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 0, '', '', ''),
        ]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], [])
        self.assertIn('positive whole number', response.data['failed'][0]['reason'])

    def test_multiple_sheets_are_all_parsed(self):
        rows_by_sheet = {
            'Sheet A': [('Set 1', 'Q1?', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', '')],
            'Sheet B': [('Set 2', 'Q2?', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', '')],
        }
        upload = make_question_template_upload(rows_by_sheet)

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['created']), 2)
        self.assertEqual(
            QuestionSet.objects.filter(assessment_level=self.level).count(), 2,
        )

    def test_sheet_with_missing_required_column_is_reported_without_aborting_other_sheets(self):
        workbook = Workbook()
        workbook.remove(workbook.active)
        bad_sheet = workbook.create_sheet('Bad Sheet')
        bad_sheet.append(['Question Set', 'Question Text'])  # missing most required columns
        bad_sheet.append(['Set 1', 'Q1?'])
        good_sheet = workbook.create_sheet('Good Sheet')
        good_sheet.append(LEVEL_QUESTION_TEMPLATE_HEADER)
        good_sheet.append(('Set 2', 'Q2?', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', ''))
        buffer = io.BytesIO()
        workbook.save(buffer)
        upload = SimpleUploadedFile('questions.xlsx', buffer.getvalue())

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['created']), 1)
        self.assertEqual(len(response.data['failed']), 1)
        self.assertIsNone(response.data['failed'][0]['row'])
        self.assertIn('Missing required column', response.data['failed'][0]['reason'])

    def test_non_xlsx_upload_returns_400(self):
        upload = SimpleUploadedFile('questions.xlsx', b'not a real workbook', content_type='text/plain')

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 400)

    def test_import_requires_a_file(self):
        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_default_import_is_additive_even_when_replace_omitted(self):
        # (a) Existing behavior unchanged: without `replace`, re-uploading
        # into a Question Set that already has questions adds to it rather
        # than touching what's there.
        existing_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        LevelQuestion.objects.create(
            question_set=existing_set, question_text='Old Q?',
            question_type=LevelQuestion.QuestionType.SINGLE_CHOICE, marks=1,
        )
        rows = [('Set 1', 'New Q?', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', '')]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(self.import_url(self.level), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['created']), 1)
        self.assertEqual(
            set(existing_set.questions.values_list('question_text', flat=True)), {'Old Q?', 'New Q?'},
        )

    def test_replace_only_touches_question_set_labels_present_in_the_file(self):
        # (b) replace=true clears prior questions in the Question Set(s) the
        # uploaded file references and imports the new rows in their place —
        # other Question Sets under the same level are left alone.
        replaced_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        old_question = LevelQuestion.objects.create(
            question_set=replaced_set, question_text='Stale Q?',
            question_type=LevelQuestion.QuestionType.SINGLE_CHOICE, marks=1,
        )
        untouched_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 2')
        LevelQuestion.objects.create(
            question_set=untouched_set, question_text='Keep me',
            question_type=LevelQuestion.QuestionType.SINGLE_CHOICE, marks=1,
        )

        rows = [('Set 1', 'Fresh Q?', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', '')]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(
            self.import_url(self.level), {'file': upload, 'replace': 'true'}, format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['created']), 1)
        self.assertFalse(LevelQuestion.objects.filter(id=old_question.id).exists())
        self.assertEqual(
            list(QuestionSet.objects.get(assessment_level=self.level, label='Set 1').questions.values_list(
                'question_text', flat=True,
            )),
            ['Fresh Q?'],
        )
        self.assertEqual(
            list(untouched_set.questions.values_list('question_text', flat=True)), ['Keep me'],
        )

    def test_replace_dry_run_reports_affected_question_and_answer_counts(self):
        replaced_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        question = LevelQuestion.objects.create(
            question_set=replaced_set, question_text='Stale Q?',
            question_type=LevelQuestion.QuestionType.SINGLE_CHOICE, marks=1,
        )
        choice = LevelChoice.objects.create(question=question, choice_text='A', is_correct=True, order=0)
        attempt = LevelAssessmentAttempt.objects.create(
            user=self.learner, assessment_level=self.level, questions_drawn=[question.id],
            submitted_at=timezone.now(),
        )
        answer = LevelAssessmentAnswer.objects.create(attempt=attempt, question=question, is_correct=True)
        answer.selected_choices.add(choice)

        rows = [('Set 1', 'Fresh Q?', 'Single Choice', 'A', 'B', 'C', 'D', '', 'A', 1, '', '', '')]
        upload = make_question_template_upload({'Sheet1': rows})

        self.auth_as(self.instructor)
        response = self.client.post(
            self.import_url(self.level), {'file': upload, 'replace': 'true', 'dry_run': 'true'}, format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['question_set_labels'], ['Set 1'])
        self.assertEqual(response.data['existing_question_count'], 1)
        self.assertEqual(response.data['affected_answer_count'], 1)
        # Dry run never mutates anything.
        self.assertTrue(LevelQuestion.objects.filter(id=question.id).exists())

    def test_replace_with_unreadable_file_leaves_existing_questions_intact(self):
        # (c) Atomicity: a whole-file read failure with replace=true must not
        # delete the level's existing questions when nothing gets imported to
        # replace them.
        existing_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        LevelQuestion.objects.create(
            question_set=existing_set, question_text='Keep me',
            question_type=LevelQuestion.QuestionType.SINGLE_CHOICE, marks=1,
        )
        upload = SimpleUploadedFile('questions.xlsx', b'not a real workbook', content_type='text/plain')

        self.auth_as(self.instructor)
        response = self.client.post(
            self.import_url(self.level), {'file': upload, 'replace': 'true'}, format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(existing_set.questions.count(), 1)


class LevelQuestionAdminApiTests(BaseAPITestCase):
    """Question Bank admin surface: list/filter/search, view/edit, and
    delete-with-usage-warning for LevelQuestion rows (levelassessments.views.
    LevelQuestionAdminViewSet)."""

    def setUp(self):
        super().setUp()
        self.officer_level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, questions_per_attempt=2,
        )
        self.management_level = configure_assessment_level(
            self.org, User.AssessmentLevel.MANAGEMENT, questions_per_attempt=2,
        )
        self.other_org_level = configure_assessment_level(
            self.other_org, User.AssessmentLevel.OFFICER, questions_per_attempt=2,
        )

        self.officer_set = QuestionSet.objects.create(assessment_level=self.officer_level, label='Set 1')
        self.management_set = QuestionSet.objects.create(assessment_level=self.management_level, label='Set 1')
        self.other_org_set = QuestionSet.objects.create(assessment_level=self.other_org_level, label='Set 1')

        self.officer_question = self._make_question(self.officer_set, 'What is AML?', marks=2)
        self.management_question = self._make_question(self.management_set, 'What is KYC?')
        self.other_org_question = self._make_question(self.other_org_set, 'Other org question?')

    def _make_question(self, question_set, text, marks=1, question_type=LevelQuestion.QuestionType.SINGLE_CHOICE):
        question = LevelQuestion.objects.create(
            question_set=question_set, question_text=text, question_type=question_type, marks=marks,
        )
        LevelChoice.objects.create(question=question, choice_text='Option A', is_correct=True, order=0)
        LevelChoice.objects.create(question=question, choice_text='Option B', is_correct=False, order=1)
        LevelChoice.objects.create(question=question, choice_text='Option C', is_correct=False, order=2)
        LevelChoice.objects.create(question=question, choice_text='Option D', is_correct=False, order=3)
        return question

    def list_url(self, **params):
        query = '&'.join(f'{key}={value}' for key, value in params.items())
        return f'/api/level-questions/{"?" + query if query else ""}'

    # --- Scoping ---

    def test_org_admin_list_is_strictly_scoped_to_own_organization(self):
        self.auth_as(self.org_admin)
        response = self.client.get(self.list_url())
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.officer_question.id, self.management_question.id})
        self.assertNotIn(self.other_org_question.id, ids)

    def test_org_admin_organization_query_param_is_ignored(self):
        # Passing another organization's id must not leak its questions.
        self.auth_as(self.org_admin)
        response = self.client.get(self.list_url(organization=self.other_org.id))
        ids = {row['id'] for row in response.data['results']}
        self.assertNotIn(self.other_org_question.id, ids)
        self.assertEqual(ids, {self.officer_question.id, self.management_question.id})

    def test_instructor_list_is_strictly_scoped_to_own_organization(self):
        self.auth_as(self.instructor)
        response = self.client.get(self.list_url())
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.officer_question.id, self.management_question.id})

    def test_learner_cannot_access_question_bank(self):
        self.auth_as(self.learner)
        response = self.client.get(self.list_url())
        self.assertEqual(response.status_code, 403)

    # --- Platform admin filtering ---

    def test_platform_admin_can_filter_by_organization_alone(self):
        self.auth_as(self.platform_admin)
        response = self.client.get(self.list_url(organization=self.org.id))
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.officer_question.id, self.management_question.id})

    def test_platform_admin_can_filter_by_assessment_level_alone(self):
        self.auth_as(self.platform_admin)
        response = self.client.get(self.list_url(assessment_level='officer'))
        ids = {row['id'] for row in response.data['results']}
        # Narrows to every org's Officer-level questions — both self.org's and
        # other_org's — since no organization filter was given.
        self.assertEqual(ids, {self.officer_question.id, self.other_org_question.id})

    def test_platform_admin_can_combine_organization_and_assessment_level(self):
        self.auth_as(self.platform_admin)
        response = self.client.get(self.list_url(organization=self.org.id, assessment_level='officer'))
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.officer_question.id})

    # --- Search ---

    def test_search_filters_by_question_text(self):
        self.auth_as(self.org_admin)
        response = self.client.get(self.list_url(search='KYC'))
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.management_question.id})

    # --- View/Edit ---

    def test_retrieve_returns_full_editable_record(self):
        self.auth_as(self.org_admin)
        response = self.client.get(f'/api/level-questions/{self.officer_question.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['question_text'], 'What is AML?')
        self.assertEqual(response.data['options']['A'], 'Option A')
        self.assertEqual(response.data['correct_answers'], ['A'])
        self.assertEqual(response.data['marks'], 2)

    def test_edit_persists_text_options_and_feedback(self):
        self.auth_as(self.org_admin)
        payload = {
            'question_text': 'Updated question text?',
            'question_type': 'SINGLE_CHOICE',
            'options': {'A': 'New A', 'B': 'New B', 'C': 'New C', 'D': 'New D', 'E': ''},
            'correct_answers': ['B'],
            'marks': 3,
            'explanation': 'Because B is right.',
            'feedback_correct': 'Nice work.',
            'feedback_incorrect': 'Try again.',
        }
        response = self.client.patch(
            f'/api/level-questions/{self.officer_question.id}/', payload, format='json',
        )
        self.assertEqual(response.status_code, 200)

        self.officer_question.refresh_from_db()
        self.assertEqual(self.officer_question.question_text, 'Updated question text?')
        self.assertEqual(self.officer_question.marks, 3)
        self.assertEqual(self.officer_question.explanation, 'Because B is right.')
        choices = {c.choice_text: c.is_correct for c in self.officer_question.choices.all()}
        self.assertEqual(choices, {'New A': False, 'New B': True, 'New C': False, 'New D': False})

    def test_edit_rejects_correct_answer_referencing_empty_option(self):
        # Same rule the Excel import enforces (imports.validate_options) —
        # an edit must not be able to accept what the import would reject.
        self.auth_as(self.org_admin)
        payload = {
            'question_text': 'Updated?',
            'question_type': 'SINGLE_CHOICE',
            'options': {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': ''},
            'correct_answers': ['E'],
            'marks': 1,
        }
        response = self.client.patch(
            f'/api/level-questions/{self.officer_question.id}/', payload, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_edit_preserves_choice_ids_for_options_that_remain_filled(self):
        # Historical LevelAssessmentAnswer.selected_choices references must
        # survive an edit that doesn't remove the option itself.
        original_choice_a_id = self.officer_question.choices.get(order=0).id
        self.auth_as(self.org_admin)
        payload = {
            'question_text': 'Updated text only',
            'question_type': 'SINGLE_CHOICE',
            'options': {'A': 'Option A', 'B': 'Option B', 'C': 'Option C', 'D': 'Option D', 'E': ''},
            'correct_answers': ['A'],
            'marks': 2,
        }
        self.client.patch(f'/api/level-questions/{self.officer_question.id}/', payload, format='json')
        self.assertTrue(LevelChoice.objects.filter(id=original_choice_a_id).exists())

    def test_org_admin_cannot_edit_another_organizations_question(self):
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/level-questions/{self.other_org_question.id}/',
            {
                'question_text': 'Hijacked', 'question_type': 'SINGLE_CHOICE',
                'options': {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': ''},
                'correct_answers': ['A'], 'marks': 1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 404)

    # --- Usage check + delete ---

    def test_usage_check_reports_zero_for_a_never_used_question(self):
        self.auth_as(self.org_admin)
        response = self.client.get(f'/api/level-questions/{self.officer_question.id}/usage/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['attempt_count'], 0)

    def test_usage_check_reports_correct_count_for_a_used_question(self):
        LevelAssessmentAttempt.objects.create(
            user=self.learner, assessment_level=self.officer_level,
            questions_drawn=[self.officer_question.id, self.management_question.id],
            submitted_at=timezone.now(),
        )
        LevelAssessmentAttempt.objects.create(
            user=self.org_admin, assessment_level=self.officer_level,
            questions_drawn=[self.officer_question.id],
            submitted_at=timezone.now(),
        )
        self.auth_as(self.org_admin)
        response = self.client.get(f'/api/level-questions/{self.officer_question.id}/usage/')
        self.assertEqual(response.data['attempt_count'], 2)

    def test_delete_of_never_used_question_succeeds(self):
        self.auth_as(self.org_admin)
        response = self.client.delete(f'/api/level-questions/{self.management_question.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(LevelQuestion.objects.filter(id=self.management_question.id).exists())

    def test_deleted_question_shows_placeholder_in_past_attempt_results_without_breaking_it(self):
        attempt = LevelAssessmentAttempt.objects.create(
            user=self.learner, assessment_level=self.officer_level,
            questions_drawn=[self.officer_question.id, self.management_question.id],
            submitted_at=timezone.now(), score_percent=Decimal('50.00'),
        )
        LevelAssessmentAnswer.objects.create(
            attempt=attempt, question=self.officer_question, is_correct=True,
        )

        self.auth_as(self.org_admin)
        delete_response = self.client.delete(f'/api/level-questions/{self.management_question.id}/')
        self.assertEqual(delete_response.status_code, 204)

        self.auth_as(self.learner)
        review = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertEqual(review.status_code, 200)

        questions_by_id = {q['id']: q for q in review.data['questions']}
        self.assertFalse(questions_by_id[self.officer_question.id]['removed'])
        self.assertTrue(questions_by_id[self.management_question.id]['removed'])
        # The rest of the attempt's results are unaffected.
        self.assertEqual(review.data['score_percent'], '50.00')
        answers_by_question = {a['question']: a for a in review.data['answers']}
        self.assertTrue(answers_by_question[self.officer_question.id]['is_correct'])


class AssessmentLevelConfigApiTests(BaseAPITestCase):
    """Every org is auto-seeded four AssessmentLevel rows, read-only from this
    endpoint — pass mark / questions-per-attempt / seconds-per-question are
    now org_settings.OrganizationSettings, edited via OrganizationSettingsApiTests
    below, not per level here."""

    def test_org_has_four_seeded_levels(self):
        self.auth_as(self.org_admin)
        response = self.client.get('/api/assessment-levels/')
        names = sorted(level['name'] for level in response.data)
        self.assertEqual(names, ['assistant_supervisor', 'management', 'officer', 'senior_management'])
        self.assertTrue(all(level['organization']['id'] == self.org.id for level in response.data))

    def test_level_reflects_org_settings_values(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            pass_mark_percent=85, questions_per_attempt=20, seconds_per_question=45,
        )
        self.auth_as(self.org_admin)
        response = self.client.get('/api/assessment-levels/')
        level = next(row for row in response.data if row['name'] == User.AssessmentLevel.OFFICER)
        self.assertEqual(level['pass_threshold'], 85)
        self.assertEqual(level['questions_per_attempt'], 20)
        self.assertEqual(level['seconds_per_question'], 45)

    def test_level_reflects_org_settings_timing_mode_and_total_exam_minutes(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.FIXED_TOTAL, total_exam_minutes=90,
        )
        self.auth_as(self.org_admin)
        response = self.client.get('/api/assessment-levels/')
        level = next(row for row in response.data if row['name'] == User.AssessmentLevel.OFFICER)
        self.assertEqual(level['timing_mode'], 'FIXED_TOTAL')
        self.assertEqual(level['total_exam_minutes'], 90)

    def test_patching_a_level_is_no_longer_allowed(self):
        level = AssessmentLevel.objects.get(organization=self.org, name=User.AssessmentLevel.OFFICER)
        self.auth_as(self.org_admin)
        response = self.client.patch(f'/api/assessment-levels/{level.id}/', {'name': 'x'}, format='json')
        self.assertEqual(response.status_code, 405)


class OrganizationSettingsApiTests(BaseAPITestCase):
    """OrganizationSettings: ORG_ADMIN/PLATFORM_ADMIN-only, ORG_ADMIN scoped to
    their own organization's single row, PLATFORM_ADMIN able to list/edit any
    organization's — plus the questions_per_attempt-vs-question-pool
    validation that warns at save time instead of at attempt-start time."""

    def test_org_admin_sees_only_their_own_organizations_settings(self):
        self.auth_as(self.org_admin)
        response = self.client.get('/api/organization-settings/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['organization']['id'], self.org.id)
        self.assertEqual(response.data[0]['questions_per_attempt'], 15)
        self.assertEqual(response.data[0]['timing_mode'], 'PER_QUESTION')
        self.assertEqual(response.data[0]['seconds_per_question'], 60)
        self.assertEqual(response.data[0]['total_exam_minutes'], 15)
        self.assertEqual(response.data[0]['pass_mark_percent'], 70)

    def test_org_admin_duration_derives_seconds_per_question(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {
                'questions_per_attempt': 30,
                'total_exam_minutes': 30,
                # Both are read-only: callers cannot create contradictory
                # timing settings by supplying their own values.
                'timing_mode': 'FIXED_TOTAL',
                'seconds_per_question': 999,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.timing_mode, 'PER_QUESTION')
        self.assertEqual(settings_obj.total_exam_minutes, 30)
        self.assertEqual(settings_obj.seconds_per_question, 60)

    def test_duration_must_allow_at_least_five_seconds_per_question(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {'questions_per_attempt': 100, 'total_exam_minutes': 5},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('total_exam_minutes', response.data)

    def test_max_attempts_default_to_unlimited_and_are_independently_settable(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.assertIsNone(settings_obj.max_level_assessment_attempts)
        self.assertIsNone(settings_obj.max_course_retake_attempts)

        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {'max_level_assessment_attempts': 3, 'max_course_retake_attempts': None},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.max_level_assessment_attempts, 3)
        self.assertIsNone(settings_obj.max_course_retake_attempts)

        # And back to unlimited.
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/', {'max_level_assessment_attempts': None}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        settings_obj.refresh_from_db()
        self.assertIsNone(settings_obj.max_level_assessment_attempts)

    def test_org_admin_can_update_their_own_settings(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {'questions_per_attempt': 10, 'total_exam_minutes': 5, 'pass_mark_percent': 80},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.questions_per_attempt, 10)
        self.assertEqual(settings_obj.seconds_per_question, 30)
        self.assertEqual(settings_obj.pass_mark_percent, 80)

    def test_org_admin_cannot_update_another_organizations_settings(self):
        other_settings = OrganizationSettings.objects.get(organization=self.other_org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{other_settings.id}/', {'pass_mark_percent': 10}, format='json'
        )
        self.assertEqual(response.status_code, 404)
        other_settings.refresh_from_db()
        self.assertEqual(other_settings.pass_mark_percent, 70)

    def test_organization_field_is_read_only(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {'organization': self.other_org.id, 'pass_mark_percent': 55}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.organization_id, self.org.id)
        self.assertEqual(settings_obj.pass_mark_percent, 55)

    def test_learner_denied_both_list_and_update(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.learner)
        self.assertEqual(self.client.get('/api/organization-settings/').status_code, 403)
        self.assertEqual(
            self.client.patch(
                f'/api/organization-settings/{settings_obj.id}/', {'pass_mark_percent': 1}, format='json'
            ).status_code,
            403,
        )
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.pass_mark_percent, 70)

    def test_instructor_denied_both_list_and_update(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.instructor)
        self.assertEqual(self.client.get('/api/organization-settings/').status_code, 403)
        self.assertEqual(
            self.client.patch(
                f'/api/organization-settings/{settings_obj.id}/', {'pass_mark_percent': 1}, format='json'
            ).status_code,
            403,
        )

    def test_platform_admin_can_switch_between_two_organizations_independently(self):
        self.auth_as(self.platform_admin)
        response = self.client.get('/api/organization-settings/')
        self.assertEqual(response.status_code, 200)
        org_ids = {row['organization']['id'] for row in response.data}
        self.assertEqual(org_ids, {self.org.id, self.other_org.id})

        mine = OrganizationSettings.objects.get(organization=self.org)
        theirs = OrganizationSettings.objects.get(organization=self.other_org)

        self.client.patch(f'/api/organization-settings/{mine.id}/', {'pass_mark_percent': 90}, format='json')
        self.client.patch(f'/api/organization-settings/{theirs.id}/', {'pass_mark_percent': 40}, format='json')

        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.pass_mark_percent, 90)
        self.assertEqual(theirs.pass_mark_percent, 40)

    def test_questions_per_attempt_rejected_when_it_exceeds_a_levels_question_pool(self):
        level = AssessmentLevel.objects.get(organization=self.org, name=User.AssessmentLevel.OFFICER)
        question_set = QuestionSet.objects.create(assessment_level=level, label='Set 1')
        for i in range(3):
            LevelQuestion.objects.create(
                question_set=question_set, question_text=f'Q{i}?',
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            )

        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/', {'questions_per_attempt': 10}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('questions_per_attempt', response.data)
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.questions_per_attempt, 15)  # unchanged

    def test_questions_per_attempt_counts_duplicate_wording_only_once(self):
        level = AssessmentLevel.objects.get(organization=self.org, name=User.AssessmentLevel.OFFICER)
        question_set = QuestionSet.objects.create(assessment_level=level, label='Set 1')
        for text in ('What is AML?', ' what is aml ', '<strong>WHAT IS AML!!!</strong>'):
            LevelQuestion.objects.create(
                question_set=question_set,
                question_text=text,
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            )

        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/', {'questions_per_attempt': 2}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('1 unique', str(response.data['questions_per_attempt']))
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.questions_per_attempt, 15)

    def test_questions_per_attempt_accepted_when_every_levels_pool_is_large_enough(self):
        for level in AssessmentLevel.objects.filter(organization=self.org):
            question_set = QuestionSet.objects.create(assessment_level=level, label='Set 1')
            for i in range(5):
                LevelQuestion.objects.create(
                    question_set=question_set, question_text=f'Q{i}?',
                    question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
                )

        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/', {'questions_per_attempt': 5}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_org_admin_can_configure_both_inactivity_reminders_independently(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {
                'logged_in_inactive_reminder_enabled': True,
                'logged_in_inactive_reminder_frequency': 'monthly',
                'never_logged_in_reminder_enabled': True,
                'never_logged_in_reminder_frequency': 'fortnightly',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        settings_obj.refresh_from_db()
        self.assertTrue(settings_obj.logged_in_inactive_reminder_enabled)
        self.assertEqual(settings_obj.logged_in_inactive_reminder_frequency, 'monthly')
        self.assertTrue(settings_obj.never_logged_in_reminder_enabled)
        self.assertEqual(settings_obj.never_logged_in_reminder_frequency, 'fortnightly')

    def test_reminder_last_sent_at_fields_are_read_only(self):
        settings_obj = OrganizationSettings.objects.get(organization=self.org)
        stamp = timezone.now()
        settings_obj.logged_in_inactive_last_sent_at = stamp
        settings_obj.save(update_fields=['logged_in_inactive_last_sent_at'])

        self.auth_as(self.org_admin)
        response = self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {'logged_in_inactive_last_sent_at': None, 'never_logged_in_last_sent_at': '2020-01-01T00:00:00Z'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        settings_obj.refresh_from_db()
        self.assertEqual(settings_obj.logged_in_inactive_last_sent_at, stamp)
        self.assertIsNone(settings_obj.never_logged_in_last_sent_at)


class OrganizationSettingsCertificateThresholdTests(BaseAPITestCase):
    """Confirms certificate eligibility actually moves when an organization's
    OrganizationSettings.pass_mark_percent changes — not just a code
    read-through — replacing the old per-course certificate_pass_threshold
    field this same scenario used to exercise directly on the Course."""

    def setUp(self):
        super().setUp()
        self.enrollment = Enrollment.objects.create(
            user=self.learner, course=self.published_org_course, status=Enrollment.Status.COMPLETED,
        )
        QuizAttempt.objects.create(user=self.learner, quiz=self.quiz, attempt_number=1, passed=True, score_percent=75)

    def test_default_org_pass_mark_of_70_allows_a_75_percent_score(self):
        self.assertIsNone(certificate_ineligibility_reason(self.learner, self.published_org_course))

    def test_raising_the_orgs_pass_mark_above_the_score_blocks_the_same_certificate(self):
        OrganizationSettings.objects.filter(organization=self.org).update(pass_mark_percent=80)
        # self.org (and self.learner.organization, the same Python object)
        # cached its .settings reverse relation back when BaseAPITestCase.setUp
        # created it — the signal that seeds a new org's OrganizationSettings
        # row constructs it as OrganizationSettings(organization=self.org),
        # which Django caches onto self.org.settings too. A bulk .update()
        # like the one above never touches that in-memory cache, so without
        # this refresh the read below would silently see the stale value.
        self.org.refresh_from_db()
        reason = certificate_ineligibility_reason(self.learner, self.published_org_course)
        self.assertIsNotNone(reason)
        self.assertIn('80%', reason)

    def test_lowering_the_orgs_pass_mark_below_the_score_stays_eligible(self):
        OrganizationSettings.objects.filter(organization=self.org).update(pass_mark_percent=60)
        self.org.refresh_from_db()  # see comment above
        self.assertIsNone(certificate_ineligibility_reason(self.learner, self.published_org_course))


class InactivityReminderTests(BaseAPITestCase):
    """org_settings.services.send_due_inactivity_reminders and the
    send_inactivity_reminders management command that runs it — see
    org_settings/services.py for the full eligibility/due-check rules."""

    def setUp(self):
        super().setUp()
        self.settings_obj = OrganizationSettings.objects.get(organization=self.org)
        self.settings_obj.logged_in_inactive_reminder_enabled = True
        self.settings_obj.logged_in_inactive_reminder_frequency = OrganizationSettings.ReminderFrequency.WEEKLY
        self.settings_obj.never_logged_in_reminder_enabled = True
        self.settings_obj.never_logged_in_reminder_frequency = OrganizationSettings.ReminderFrequency.WEEKLY
        self.settings_obj.save()

        # self.learner (a BaseAPITestCase fixture) has never logged in and has
        # no activity — a clean "never logged in" candidate. Build the rest
        # of the cast explicitly.
        self.never_logged_in = User.objects.create_user(
            email='never-logged-in@acme.test', password='pass12345', role=User.Role.LEARNER,
            organization=self.org, is_demo=False, must_reset_password=True,
            first_name='Nina', last_name='NeverIn',
        )
        self.logged_in_inactive = User.objects.create_user(
            email='logged-in-inactive@acme.test', password='pass12345', role=User.Role.LEARNER,
            organization=self.org, is_demo=False, must_reset_password=False,
            first_name='Ian', last_name='Inactive', last_login=timezone.now(),
        )
        self.engaged_learner = User.objects.create_user(
            email='engaged@acme.test', password='pass12345', role=User.Role.LEARNER,
            organization=self.org, is_demo=False, must_reset_password=False,
            first_name='Emma', last_name='Engaged', last_login=timezone.now(),
        )
        Enrollment.objects.create(
            user=self.engaged_learner, course=self.published_org_course, status=Enrollment.Status.COMPLETED,
        )
        self.deactivated_never_logged_in = User.objects.create_user(
            email='deactivated@acme.test', password='pass12345', role=User.Role.LEARNER,
            organization=self.org, is_demo=False, is_active=False,
        )

    def test_never_logged_in_and_logged_in_inactive_each_get_distinct_correct_emails(self):
        summaries = send_due_inactivity_reminders()

        never_logged_in_email = next(m for m in mail.outbox if m.to == [self.never_logged_in.email])
        logged_in_inactive_email = next(m for m in mail.outbox if m.to == [self.logged_in_inactive.email])

        # Never-logged-in: must_reset_password was True, so a fresh temp
        # password is generated, set on the account, and included.
        self.assertIn('Temporary Password:', never_logged_in_email.body)
        self.never_logged_in.refresh_from_db()
        self.assertTrue(self.never_logged_in.check_password(
            never_logged_in_email.body.split('Temporary Password: ')[1].split('\n')[0]
        ))

        # Logged-in-but-inactive: a plain nudge, no password/credentials at all.
        self.assertNotIn('Temporary Password', logged_in_inactive_email.body)
        self.assertIn('assigned', logged_in_inactive_email.body.lower())

        reminder_types = {s['reminder_type'] for s in summaries}
        self.assertEqual(reminder_types, {'logged_in_inactive', 'never_logged_in'})

    def test_never_logged_in_with_a_real_password_gets_an_unmodified_access_reminder(self):
        already_has_password = User.objects.create_user(
            email='has-password@acme.test', password='RealPassword123!', role=User.Role.LEARNER,
            organization=self.org, is_demo=False, must_reset_password=False,
        )
        send_due_inactivity_reminders()

        email = next(m for m in mail.outbox if m.to == [already_has_password.email])
        self.assertNotIn('Temporary Password', email.body)
        already_has_password.refresh_from_db()
        self.assertTrue(already_has_password.check_password('RealPassword123!'))

    def test_engaged_learner_and_deactivated_staff_receive_nothing(self):
        send_due_inactivity_reminders()
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertNotIn(self.engaged_learner.email, recipients)
        self.assertNotIn(self.deactivated_never_logged_in.email, recipients)

    def test_org_admin_and_instructor_are_never_sent_reminders(self):
        send_due_inactivity_reminders()
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertNotIn(self.org_admin.email, recipients)
        self.assertNotIn(self.instructor.email, recipients)

    def test_a_learner_who_only_has_a_level_assessment_attempt_is_also_excluded(self):
        # Zero completed courses but a level-assessment attempt still counts
        # as "engaged" — excluded from the logged-in-inactive batch too.
        level = AssessmentLevel.objects.get(organization=self.org, name=User.AssessmentLevel.OFFICER)
        self.logged_in_inactive.assessment_level = User.AssessmentLevel.OFFICER
        self.logged_in_inactive.save()
        LevelAssessmentAttempt.objects.create(
            user=self.logged_in_inactive, assessment_level=level, submitted_at=timezone.now(),
            score_percent=40, passed=False,
        )

        send_due_inactivity_reminders()
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertNotIn(self.logged_in_inactive.email, recipients)

    def test_last_sent_at_updates_and_a_same_day_rerun_does_not_resend(self):
        send_due_inactivity_reminders()
        self.settings_obj.refresh_from_db()
        first_logged_in_sent_at = self.settings_obj.logged_in_inactive_last_sent_at
        first_never_sent_at = self.settings_obj.never_logged_in_last_sent_at
        self.assertIsNotNone(first_logged_in_sent_at)
        self.assertIsNotNone(first_never_sent_at)

        mail.outbox.clear()
        second_summaries = send_due_inactivity_reminders()
        self.assertEqual(second_summaries, [])
        self.assertEqual(len(mail.outbox), 0)
        self.settings_obj.refresh_from_db()
        self.assertEqual(self.settings_obj.logged_in_inactive_last_sent_at, first_logged_in_sent_at)
        self.assertEqual(self.settings_obj.never_logged_in_last_sent_at, first_never_sent_at)

    def test_reminder_resends_once_its_frequency_period_has_elapsed(self):
        send_due_inactivity_reminders()
        self.settings_obj.refresh_from_db()
        self.settings_obj.logged_in_inactive_last_sent_at = timezone.now() - timedelta(days=8)
        self.settings_obj.never_logged_in_last_sent_at = timezone.now() - timedelta(days=1)
        self.settings_obj.save()
        mail.outbox.clear()

        summaries = send_due_inactivity_reminders()
        reminder_types = {s['reminder_type'] for s in summaries}
        # Weekly logged-in-inactive is now overdue (8 days); weekly
        # never-logged-in is not (only 1 day) — only the former resends.
        self.assertEqual(reminder_types, {'logged_in_inactive'})

    def test_a_user_who_logs_in_and_starts_a_course_is_excluded_from_the_next_batch(self):
        # A never-logged-in user who then logs in and enrolls (but hasn't
        # completed anything yet) must drop out of BOTH batches — not
        # never-logged-in (they've logged in now) and not logged-in-inactive
        # either, since "inactive" here specifically means zero completions
        # and zero level-assessment attempts, and this user still has neither
        # — wait, they *have* logged in with zero completions, so they
        # correctly land in the logged-in-inactive batch instead.
        self.never_logged_in.last_login = timezone.now()
        self.never_logged_in.save()
        Enrollment.objects.create(
            user=self.never_logged_in, course=self.published_org_course, status=Enrollment.Status.IN_PROGRESS,
        )

        send_due_inactivity_reminders()
        never_logged_in_recipients = {addr for m in mail.outbox for addr in m.to if 'Temporary Password' in m.body}
        self.assertNotIn(self.never_logged_in.email, never_logged_in_recipients)
        logged_in_inactive_recipients = {addr for m in mail.outbox for addr in m.to if 'Temporary Password' not in m.body}
        self.assertIn(self.never_logged_in.email, logged_in_inactive_recipients)

    def test_disabled_reminder_sends_nothing_for_that_organization(self):
        self.settings_obj.logged_in_inactive_reminder_enabled = False
        self.settings_obj.never_logged_in_reminder_enabled = False
        self.settings_obj.save()

        summaries = send_due_inactivity_reminders()
        self.assertEqual(summaries, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_other_organizations_are_unaffected_by_this_organizations_settings(self):
        # other_org's own settings have both reminders off by default.
        send_due_inactivity_reminders()
        recipients = {addr for m in mail.outbox for addr in m.to}
        self.assertNotIn(self.other_org_learner.email, recipients)

    def test_management_command_runs_end_to_end(self):
        out = io.StringIO()
        call_command('send_inactivity_reminders', stdout=out)
        output = out.getvalue()
        self.assertIn('logged-in-but-inactive', output)
        self.assertIn('never-logged-in', output)
        self.assertTrue(any(m.to == [self.never_logged_in.email] for m in mail.outbox))


def make_staff_upload(rows, *, filename='staff.xlsx', title_row=True, org_name='Acme Bank'):
    """Builds an .xlsx matching the LBBL staff-enrollment template shape:
    optional title row, then the header, then `rows` (each a dict)."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Staff Details'
    if title_row:
        sheet.append([f'{org_name} - Staff Enrollment Details'])
    header = ['Full Name', 'Email Address', 'Corporate Title', 'Functional Title',
              'Branch / Department', 'Assessment Level', 'Phone Number (optional)', 'Organization']
    sheet.append(header)
    for row in rows:
        sheet.append([
            row.get('name', ''), row.get('email', ''), row.get('corporate_title', ''),
            row.get('functional_title', ''), row.get('branch', ''), row.get('level', ''),
            row.get('phone', ''), row.get('org', org_name),
        ])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return SimpleUploadedFile(
        filename, buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


class StaffEnrollmentApiTests(BaseAPITestCase):
    URL = '/api/staff/bulk/'

    def test_org_admin_enrolls_staff_as_real_learners_with_assessment_level(self):
        upload = make_staff_upload([
            {'name': 'Sunita Karki', 'email': 'sunita@acme.test', 'level': 'Front-Line Level', 'phone': '9801234567'},
            {'name': 'Bikash Thapa', 'email': 'bikash@acme.test', 'level': 'Officer'},
        ])
        self.auth_as(self.org_admin)
        response = self.client.post(self.URL, {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data['created']), 2)
        self.assertEqual(response.data['failed'], [])

        sunita = User.objects.get(email='sunita@acme.test')
        self.assertEqual(sunita.role, User.Role.LEARNER)
        self.assertFalse(sunita.is_demo)
        self.assertTrue(sunita.must_reset_password)
        self.assertEqual(sunita.assessment_level, User.AssessmentLevel.ASSISTANT_SUPERVISOR)
        self.assertEqual(sunita.organization, self.org)
        self.assertEqual(sunita.phone_number, '9801234567')

    def test_assigned_assessment_level_resolves_for_an_enrolled_staff_member(self):
        configure_assessment_level(self.org, User.AssessmentLevel.MANAGEMENT, questions_per_attempt=1)
        upload = make_staff_upload([
            {'name': 'Anita Shrestha', 'email': 'anita@acme.test', 'level': 'Middle Management Level'},
        ])
        self.auth_as(self.org_admin)
        self.client.post(self.URL, {'file': upload}, format='multipart')

        anita = User.objects.get(email='anita@acme.test')
        self.auth_as(anita)
        response = self.client.get('/api/my-assessment-level/')
        self.assertTrue(response.data['assigned'])
        self.assertEqual(response.data['assessment_level']['name'], User.AssessmentLevel.MANAGEMENT)

    def test_invalid_level_and_missing_fields_are_reported_not_dropped(self):
        upload = make_staff_upload([
            {'name': 'Good Row', 'email': 'good@acme.test', 'level': 'Officer'},
            {'name': 'Bad Level', 'email': 'bad@acme.test', 'level': 'Wizard'},
            {'name': '', 'email': 'noname@acme.test', 'level': 'Officer'},
        ])
        self.auth_as(self.org_admin)
        response = self.client.post(self.URL, {'file': upload}, format='multipart')
        self.assertEqual(len(response.data['created']), 1)
        reasons = {f['email']: f['reason'] for f in response.data['failed']}
        self.assertIn('bad@acme.test', reasons)
        self.assertIn('noname@acme.test', reasons)

    def test_org_admin_cannot_enroll_into_another_organization(self):
        upload = make_staff_upload(
            [{'name': 'X', 'email': 'x@other.test', 'level': 'Officer', 'org': 'Other Bank'}], org_name='Other Bank'
        )
        self.auth_as(self.org_admin)
        response = self.client.post(self.URL, {'file': upload}, format='multipart')
        self.assertEqual(len(response.data['created']), 0)
        self.assertFalse(User.objects.filter(email='x@other.test').exists())

    def test_platform_admin_can_enroll_into_any_organization(self):
        upload = make_staff_upload(
            [{'name': 'Y', 'email': 'y@other.test', 'level': 'Officer', 'org': 'Other Bank'}], org_name='Other Bank'
        )
        self.auth_as(self.platform_admin)
        response = self.client.post(self.URL, {'file': upload}, format='multipart')
        self.assertEqual(len(response.data['created']), 1, response.data)
        self.assertEqual(User.objects.get(email='y@other.test').organization, self.other_org)

    def test_learner_and_instructor_are_forbidden(self):
        upload = make_staff_upload([{'name': 'Z', 'email': 'z@acme.test', 'level': 'Officer'}])
        for user in (self.learner, self.instructor):
            self.auth_as(user)
            response = self.client.post(self.URL, {'file': upload}, format='multipart')
            self.assertEqual(response.status_code, 403)

    def test_csv_is_also_accepted(self):
        csv_bytes = (
            'Full Name,Email Address,Assessment Level,Organization\r\n'
            'Ram Gurung,ram@acme.test,Top Management Level,Acme Bank\r\n'
        ).encode('utf-8')
        upload = SimpleUploadedFile('staff.csv', csv_bytes, content_type='text/csv')
        self.auth_as(self.org_admin)
        response = self.client.post(self.URL, {'file': upload}, format='multipart')
        self.assertEqual(len(response.data['created']), 1, response.data)
        self.assertEqual(
            User.objects.get(email='ram@acme.test').assessment_level, User.AssessmentLevel.SENIOR_MANAGEMENT
        )


class StaffManagementApiTests(BaseAPITestCase):
    """Individual staff enrollment, the searchable/paginated staff list, and
    deactivate/reactivate (accounts.views.StaffEnrollmentViewSet)."""

    URL = '/api/staff/'

    def setUp(self):
        super().setUp()
        cache.clear()  # isolate the login-throttle counter used below

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def make_staff(self, email, **extra):
        payload = {
            'name': 'Default Name',
            'email': email,
            'corporate_title': 'Officer',
            'functional_title': 'Compliance Officer',
            'branch_department': 'Head Office',
            'assessment_level': 'Officer Level',
            'phone_number': '9800000000',
            **extra,
        }
        return self.client.post(self.URL, payload, format='json')

    def test_individual_create_behaves_identically_to_a_bulk_row(self):
        self.auth_as(self.org_admin)
        response = self.make_staff('sunita@acme.test', name='Sunita Karki')
        self.assertEqual(response.status_code, 201, response.data)

        user = User.objects.get(email='sunita@acme.test')
        self.assertEqual(user.role, User.Role.LEARNER)
        self.assertFalse(user.is_demo)
        self.assertTrue(user.must_reset_password)
        self.assertEqual(user.organization, self.org)
        self.assertEqual(user.assessment_level, User.AssessmentLevel.OFFICER)
        self.assertEqual(user.corporate_title, 'Officer')
        self.assertEqual(user.branch_department, 'Head Office')

        # Same invite email as a bulk-uploaded row.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].body)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.STAFF_ENROLLED, object_id=str(user.id)).exists())

    def test_individual_create_rejects_duplicate_email(self):
        self.auth_as(self.org_admin)
        self.assertEqual(self.make_staff('dupe@acme.test').status_code, 201)
        response = self.make_staff('dupe@acme.test')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already exists', str(response.data))

    def test_individual_create_rejects_invalid_assessment_level(self):
        self.auth_as(self.org_admin)
        response = self.make_staff('bad-level@acme.test', assessment_level='Wizard')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Assessment Level', str(response.data))
        self.assertFalse(User.objects.filter(email='bad-level@acme.test').exists())

    def test_org_admin_cannot_target_another_organization(self):
        # No organization field is exposed to an ORG_ADMIN's request at all —
        # it's always their own, server-side.
        self.auth_as(self.org_admin)
        response = self.make_staff('own-org@acme.test', organization=self.other_org.id)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.get(email='own-org@acme.test').organization, self.org)

    def test_platform_admin_must_name_an_organization(self):
        self.auth_as(self.platform_admin)
        response = self.make_staff('no-org@other.test')
        self.assertEqual(response.status_code, 400)

        response = self.make_staff('with-org@other.test', organization=self.other_org.id)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.get(email='with-org@other.test').organization, self.other_org)

    def test_list_search_by_partial_name_and_partial_email(self):
        self.auth_as(self.org_admin)
        self.make_staff('bikash.thapa@acme.test', name='Bikash Thapa')
        self.make_staff('anita.shrestha@acme.test', name='Anita Shrestha')

        by_name = self.client.get(self.URL, {'search': 'bikash'})
        self.assertEqual([r['email'] for r in by_name.data['results']], ['bikash.thapa@acme.test'])

        by_email = self.client.get(self.URL, {'search': 'shrestha@acme'})
        self.assertEqual([r['email'] for r in by_email.data['results']], ['anita.shrestha@acme.test'])

    def test_list_is_paginated_and_does_not_dump_the_whole_roster(self):
        # self.org already has one non-demo LEARNER from BaseAPITestCase's own
        # fixture (self.learner) — created staff are on top of that.
        self.auth_as(self.org_admin)
        for i in range(3):
            self.make_staff(f'staff{i}@acme.test', name=f'Staff {i}')

        response = self.client.get(self.URL, {'page_size': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['count'], 4)
        self.assertIsNotNone(response.data['next'])

    def test_list_defaults_to_active_and_status_filter_shows_deactivated(self):
        self.auth_as(self.org_admin)
        self.make_staff('active@acme.test', name='Active Person')
        self.make_staff('inactive@acme.test', name='Inactive Person')
        inactive_user = User.objects.get(email='inactive@acme.test')
        self.client.post(f'{self.URL}{inactive_user.id}/deactivate/')

        active_list = self.client.get(self.URL)
        active_emails = [r['email'] for r in active_list.data['results']]
        self.assertIn('active@acme.test', active_emails)
        self.assertNotIn('inactive@acme.test', active_emails)

        inactive_list = self.client.get(self.URL, {'status': 'inactive'})
        self.assertEqual([r['email'] for r in inactive_list.data['results']], ['inactive@acme.test'])

    def test_org_admin_staff_list_never_shows_another_organizations_staff(self):
        self.auth_as(self.platform_admin)
        self.make_staff('other-org-staff@other.test', organization=self.other_org.id, name='Other Org Staff')

        self.auth_as(self.org_admin)
        response = self.client.get(self.URL)
        self.assertNotIn('other-org-staff@other.test', [r['email'] for r in response.data['results']])

    def test_deactivate_blocks_login_hides_from_active_list_and_leaderboard_but_preserves_history(self):
        self.auth_as(self.org_admin)
        create_response = self.make_staff('veteran@acme.test', name='Veteran Learner')
        staff_id = create_response.data['id']
        staff = User.objects.get(id=staff_id)
        staff.set_password('pass12345')
        staff.save()

        # Give them a completed course, a certificate, and a leaderboard entry.
        Enrollment.objects.create(user=staff, course=self.published_org_course, status=Enrollment.Status.COMPLETED)
        QuizAttempt.objects.create(user=staff, quiz=self.quiz, attempt_number=1, passed=True, score_percent=100)
        certificate = generate_certificate(staff, self.published_org_course)
        recalculate_leaderboard_entry(staff)
        self.assertTrue(LeaderboardEntry.objects.filter(user=staff).exists())

        # Deactivate.
        self.auth_as(self.org_admin)
        deactivate_response = self.client.post(f'{self.URL}{staff_id}/deactivate/')
        self.assertEqual(deactivate_response.status_code, 200)
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.STAFF_DEACTIVATED, object_id=str(staff.id)).exists()
        )

        # Login is blocked.
        login_response = self.client.post('/api/auth/login/', {'email': staff.email, 'password': 'pass12345'})
        self.assertEqual(login_response.status_code, 401)

        # Gone from the active staff list...
        self.auth_as(self.org_admin)
        active_list = self.client.get(self.URL)
        self.assertNotIn(staff.email, [r['email'] for r in active_list.data['results']])

        # ...and from the leaderboard.
        self.auth_as(self.learner)
        leaderboard = self.client.get('/api/leaderboard/')
        self.assertNotIn(staff.id, [row['user_id'] for row in leaderboard.data])

        # But their history is untouched and still queryable by an admin.
        self.assertTrue(Enrollment.objects.filter(user=staff, status=Enrollment.Status.COMPLETED).exists())
        self.assertTrue(Certificate.objects.filter(id=certificate.id, user=staff).exists())
        self.assertTrue(LeaderboardEntry.objects.filter(user=staff).exists())

        self.auth_as(self.org_admin)
        certificates_response = self.client.get('/api/certificates/')
        self.assertIn(certificate.id, [c['id'] for c in certificates_response.data])

    def test_reactivate_restores_login_without_touching_history(self):
        self.auth_as(self.org_admin)
        create_response = self.make_staff('comeback@acme.test', name='Comeback Kid')
        staff_id = create_response.data['id']
        staff = User.objects.get(id=staff_id)
        staff.set_password('pass12345')
        staff.save()
        Enrollment.objects.create(user=staff, course=self.published_org_course, status=Enrollment.Status.COMPLETED)

        self.client.post(f'{self.URL}{staff_id}/deactivate/')
        reactivate_response = self.client.post(f'{self.URL}{staff_id}/reactivate/')
        self.assertEqual(reactivate_response.status_code, 200)
        staff.refresh_from_db()
        self.assertTrue(staff.is_active)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.STAFF_REACTIVATED, object_id=str(staff.id)).exists()
        )

        login_response = self.client.post('/api/auth/login/', {'email': staff.email, 'password': 'pass12345'})
        self.assertEqual(login_response.status_code, 200)

        self.auth_as(self.org_admin)
        active_list = self.client.get(self.URL)
        self.assertIn(staff.email, [r['email'] for r in active_list.data['results']])
        self.assertTrue(Enrollment.objects.filter(user=staff, status=Enrollment.Status.COMPLETED).exists())

    def test_learner_and_instructor_are_forbidden_from_staff_management(self):
        for user in (self.learner, self.instructor):
            self.auth_as(user)
            self.assertEqual(self.client.get(self.URL).status_code, 403)
            self.assertEqual(self.make_staff(f'blocked-{user.id}@acme.test').status_code, 403)


class LevelAssessmentStudentFlowApiTests(BaseAPITestCase):
    """
    The student-facing flow: dashboard/landing status lookup, starting an
    attempt (random draw, answer-key stripped), submitting it for grading
    (answer-key revealed per-answer only after submission), and the
    resulting status transitions (Not started -> In progress -> Passed/Failed
    -> retake available).
    """

    def setUp(self):
        super().setUp()
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=2,
        )
        question_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')

        self.q1 = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q1?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        self.q1_correct = LevelChoice.objects.create(question=self.q1, choice_text='A', is_correct=True)
        LevelChoice.objects.create(question=self.q1, choice_text='B', is_correct=False)

        self.q2 = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q2?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        self.q2_correct = LevelChoice.objects.create(question=self.q2, choice_text='A', is_correct=True)
        LevelChoice.objects.create(question=self.q2, choice_text='B', is_correct=False)

        self.q3 = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q3?', question_type=LevelQuestion.QuestionType.MULTIPLE_ANSWER,
            marks=2,
        )
        self.q3_correct_a = LevelChoice.objects.create(question=self.q3, choice_text='A', is_correct=True)
        self.q3_correct_b = LevelChoice.objects.create(question=self.q3, choice_text='B', is_correct=True)
        LevelChoice.objects.create(question=self.q3, choice_text='C', is_correct=False)

        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save()

    def correct_choice_ids_for(self, question_id):
        return list(LevelQuestion.objects.get(id=question_id).choices.filter(is_correct=True).values_list('id', flat=True))

    def start_attempt(self):
        self.auth_as(self.learner)
        return self.client.post('/api/level-attempts/start/')

    def submit_all_correct(self, attempt_id, questions):
        answers = [{'question': q['id'], 'selected_choices': self.correct_choice_ids_for(q['id'])} for q in questions]
        return self.client.post(f'/api/level-attempts/{attempt_id}/submit/', {'answers': answers}, format='json')

    def test_not_assigned_when_user_has_no_assessment_level(self):
        self.learner.assessment_level = None
        self.learner.save()
        self.auth_as(self.learner)

        response = self.client.get('/api/my-assessment-level/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'assigned': False})

    def test_not_assigned_when_user_has_no_organization(self):
        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.organization = None
        self.learner.save()
        self.auth_as(self.learner)

        response = self.client.get('/api/my-assessment-level/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'assigned': False})

    def test_assigned_to_own_organizations_level_not_another_orgs(self):
        # Every org now has all four levels (seeded on creation), so a learner
        # with an assessment_level set is always assigned — to their own org's.
        self.other_org_learner.assessment_level = User.AssessmentLevel.OFFICER
        self.other_org_learner.save()
        self.auth_as(self.other_org_learner)

        response = self.client.get('/api/my-assessment-level/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['assigned'])
        self.assertEqual(
            response.data['assessment_level']['organization']['id'], self.other_org_learner.organization_id
        )

    def test_status_not_started_before_any_attempt(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/my-assessment-level/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['assigned'])
        self.assertEqual(response.data['status'], 'NOT_STARTED')
        self.assertIsNone(response.data['open_attempt_id'])
        self.assertEqual(response.data['assessment_level']['questions_per_attempt'], 2)

    def test_start_draws_the_configured_number_with_no_answer_key_exposed(self):
        response = self.start_attempt()

        self.assertEqual(response.status_code, 201)
        questions = response.data['questions']
        self.assertEqual(len(questions), 2)
        for question in questions:
            for choice in question['choices']:
                self.assertNotIn('is_correct', choice)
        self.assertEqual(response.data['answers'], [])

    def test_status_in_progress_after_starting_and_blocks_a_second_start(self):
        self.start_attempt()

        status_response = self.client.get('/api/my-assessment-level/')
        self.assertEqual(status_response.data['status'], 'IN_PROGRESS')
        self.assertIsNotNone(status_response.data['open_attempt_id'])

        second_start = self.client.post('/api/level-attempts/start/')
        self.assertEqual(second_start.status_code, 400)

    def test_submit_all_correct_passes_and_reveals_answer_key(self):
        start_response = self.start_attempt()
        attempt_id = start_response.data['id']
        questions = start_response.data['questions']

        response = self.submit_all_correct(attempt_id, questions)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['passed'])
        self.assertEqual(Decimal(response.data['score_percent']), Decimal('100.00'))
        for answer in response.data['answers']:
            self.assertTrue(answer['is_correct'])
            self.assertEqual(set(answer['correct_choice_ids']), set(answer['selected_choices']))

        status_response = self.client.get('/api/my-assessment-level/')
        self.assertEqual(status_response.data['status'], 'PASSED')
        self.assertIsNone(status_response.data['open_attempt_id'])

    def test_submit_all_wrong_fails(self):
        start_response = self.start_attempt()
        attempt_id = start_response.data['id']
        questions = start_response.data['questions']

        answers = []
        for question in questions:
            wrong_choice = next(
                c['id'] for c in question['choices'] if c['id'] not in self.correct_choice_ids_for(question['id'])
            )
            answers.append({'question': question['id'], 'selected_choices': [wrong_choice]})
        response = self.client.post(f'/api/level-attempts/{attempt_id}/submit/', {'answers': answers}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['passed'])

        status_response = self.client.get('/api/my-assessment-level/')
        self.assertEqual(status_response.data['status'], 'FAILED')

    def test_retake_allowed_after_submission_with_fresh_draw(self):
        start_response = self.start_attempt()
        self.submit_all_correct(start_response.data['id'], start_response.data['questions'])

        second_start = self.client.post('/api/level-attempts/start/')
        self.assertEqual(second_start.status_code, 201)
        self.assertNotEqual(second_start.data['id'], start_response.data['id'])

    def test_cannot_submit_answers_missing_a_drawn_question(self):
        start_response = self.start_attempt()
        attempt_id = start_response.data['id']
        questions = start_response.data['questions']

        answers = [{'question': questions[0]['id'], 'selected_choices': self.correct_choice_ids_for(questions[0]['id'])}]
        response = self.client.post(f'/api/level-attempts/{attempt_id}/submit/', {'answers': answers}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_cannot_submit_a_question_not_drawn_for_this_attempt(self):
        start_response = self.start_attempt()
        attempt_id = start_response.data['id']
        questions = start_response.data['questions']
        drawn_ids = {q['id'] for q in questions}
        not_drawn = next(q for q in (self.q1, self.q2, self.q3) if q.id not in drawn_ids)

        answers = [{'question': q['id'], 'selected_choices': self.correct_choice_ids_for(q['id'])} for q in questions]
        answers[0]['question'] = not_drawn.id
        response = self.client.post(f'/api/level-attempts/{attempt_id}/submit/', {'answers': answers}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_cannot_submit_the_same_attempt_twice(self):
        start_response = self.start_attempt()
        self.submit_all_correct(start_response.data['id'], start_response.data['questions'])

        second_submit = self.client.post(f'/api/level-attempts/{start_response.data["id"]}/submit/', {'answers': []}, format='json')
        self.assertEqual(second_submit.status_code, 400)

    def test_another_user_cannot_view_or_submit_someone_elses_attempt(self):
        start_response = self.start_attempt()
        attempt_id = start_response.data['id']

        self.other_org_learner.organization = self.org
        self.other_org_learner.assessment_level = User.AssessmentLevel.OFFICER
        self.other_org_learner.save()
        self.auth_as(self.other_org_learner)

        get_response = self.client.get(f'/api/level-attempts/{attempt_id}/')
        self.assertEqual(get_response.status_code, 404)

        submit_response = self.client.post(f'/api/level-attempts/{attempt_id}/submit/', {'answers': []}, format='json')
        self.assertEqual(submit_response.status_code, 404)

    def test_start_requires_an_assigned_assessment_level(self):
        self.learner.assessment_level = None
        self.learner.save()
        response = self.start_attempt()
        self.assertEqual(response.status_code, 400)


class LevelAssessmentPreviewApiTests(BaseAPITestCase):
    """
    Admin-only content-review preview (AssessmentLevelViewSet.preview) —
    simulates one real attempt's random draw, answer key included, without
    ever creating a LevelAssessmentAttempt row. See courses/SlidePlayer's own
    preview-mode tests for the equivalent course-content guarantee.
    """

    def setUp(self):
        super().setUp()
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=2,
        )
        question_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        self.q1 = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q1?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        LevelChoice.objects.create(question=self.q1, choice_text='A', is_correct=True, order=0)
        LevelChoice.objects.create(question=self.q1, choice_text='B', is_correct=False, order=1)
        self.q2 = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q2?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        LevelChoice.objects.create(question=self.q2, choice_text='A', is_correct=True, order=0)
        LevelChoice.objects.create(question=self.q2, choice_text='B', is_correct=False, order=1)

    def preview(self):
        return self.client.post(f'/api/assessment-levels/{self.level.id}/preview/')

    def test_learner_cannot_preview(self):
        self.auth_as(self.learner)
        response = self.preview()
        self.assertEqual(response.status_code, 403)

    def test_instructor_org_admin_and_platform_admin_can_preview(self):
        for user in (self.instructor, self.org_admin, self.platform_admin):
            self.auth_as(user)
            response = self.preview()
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(len(response.data['questions']), 2)

    def test_preview_reveals_the_answer_key(self):
        self.auth_as(self.org_admin)
        response = self.preview()

        self.assertEqual(response.status_code, 200)
        for question in response.data['questions']:
            self.assertIn('correct_answers', question)
            self.assertTrue(question['correct_answers'])

    def test_preview_never_creates_a_level_assessment_attempt(self):
        self.auth_as(self.org_admin)

        self.preview()
        self.preview()
        self.preview()

        self.assertEqual(LevelAssessmentAttempt.objects.count(), 0)

    def test_preview_does_not_affect_a_real_attempts_max_attempts_count(self):
        OrganizationSettings.objects.filter(organization=self.org).update(max_level_assessment_attempts=1)
        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save()

        self.auth_as(self.org_admin)
        self.preview()
        self.preview()

        self.auth_as(self.learner)
        start_response = self.client.post('/api/level-attempts/start/')
        self.assertEqual(start_response.status_code, 201, start_response.data)


class LevelAssessmentMaxAttemptsTests(BaseAPITestCase):
    """OrganizationSettings.max_level_assessment_attempts (null = unlimited,
    the original behavior) — see levelassessments.services.
    start_level_assessment_attempt/level_assessment_attempts_remaining."""

    def setUp(self):
        super().setUp()
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=1,
        )
        question_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        self.question = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        LevelChoice.objects.create(question=self.question, choice_text='Correct', is_correct=True)
        self.wrong_choice = LevelChoice.objects.create(question=self.question, choice_text='Wrong', is_correct=False)

        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save()
        self.auth_as(self.learner)

    def fail_one_attempt(self):
        start = self.client.post('/api/level-attempts/start/')
        self.assertEqual(start.status_code, 201, start.data)
        attempt_id = start.data['id']
        question_id = start.data['questions'][0]['id']
        return self.client.post(
            f'/api/level-attempts/{attempt_id}/submit/',
            {'answers': [{'question': question_id, 'selected_choices': [self.wrong_choice.id]}]},
            format='json',
        )

    def test_unlimited_by_default_allows_many_attempts(self):
        for _ in range(5):
            response = self.fail_one_attempt()
            self.assertEqual(response.status_code, 200)

        status_response = self.client.get('/api/my-assessment-level/')
        self.assertIsNone(status_response.data['attempts_remaining'])

    def test_cap_reached_blocks_further_attempts_and_is_reflected_in_status(self):
        OrganizationSettings.objects.filter(organization=self.org).update(max_level_assessment_attempts=2)

        first = self.fail_one_attempt()
        self.assertEqual(first.status_code, 200)
        status_after_first = self.client.get('/api/my-assessment-level/')
        self.assertEqual(status_after_first.data['attempts_remaining'], 1)

        second = self.fail_one_attempt()
        self.assertEqual(second.status_code, 200)
        status_after_second = self.client.get('/api/my-assessment-level/')
        self.assertEqual(status_after_second.data['attempts_remaining'], 0)

        third_start = self.client.post('/api/level-attempts/start/')
        self.assertEqual(third_start.status_code, 400)
        self.assertIn('maximum', third_start.data['detail'].lower())

    def test_other_organization_is_unaffected_by_this_orgs_cap(self):
        OrganizationSettings.objects.filter(organization=self.org).update(max_level_assessment_attempts=1)
        self.fail_one_attempt()

        self.other_org_learner.organization = self.org  # move into the capped org to reuse fail_one_attempt
        self.other_org_learner.assessment_level = User.AssessmentLevel.OFFICER
        self.other_org_learner.save()
        self.auth_as(self.other_org_learner)
        # A different USER in the same capped org still gets their own count.
        response = self.client.post('/api/level-attempts/start/')
        self.assertEqual(response.status_code, 201)


class LevelAssessmentResumeTests(BaseAPITestCase):
    """
    Resuming an in-progress attempt after a browser crash/closure/lost
    connection — levelassessments.services.resume_level_assessment_attempt,
    plus the save-answer/advance progress-tracking actions it depends on.
    """

    def setUp(self):
        super().setUp()
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=3,
        )
        question_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        self.questions = []
        self.correct_choices = []
        for i in range(3):
            question = LevelQuestion.objects.create(
                question_set=question_set, question_text=f'Q{i}?',
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE, marks=1,
            )
            correct = LevelChoice.objects.create(question=question, choice_text='Correct', is_correct=True)
            LevelChoice.objects.create(question=question, choice_text='Wrong', is_correct=False)
            self.questions.append(question)
            self.correct_choices.append(correct)

        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save()
        self.auth_as(self.learner)

    def start_attempt(self):
        response = self.client.post('/api/level-attempts/start/')
        self.assertEqual(response.status_code, 201, response.data)
        attempt = LevelAssessmentAttempt.objects.get(id=response.data['id'])
        return attempt

    def test_fresh_attempt_starts_at_question_zero_with_full_remaining_time(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.PER_QUESTION, seconds_per_question=90,
        )
        attempt = self.start_attempt()

        response = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertEqual(response.data['current_question_index'], 0)
        self.assertGreaterEqual(response.data['remaining_seconds'], 89)
        self.assertLessEqual(response.data['remaining_seconds'], 90)

    def test_save_answer_persists_selection_without_creating_a_graded_answer_row(self):
        attempt = self.start_attempt()
        question_id = attempt.questions_drawn[0]
        choice_id = self.correct_choices[self.questions.index(LevelQuestion.objects.get(id=question_id))].id

        response = self.client.post(
            f'/api/level-attempts/{attempt.id}/save-answer/',
            {'question': question_id, 'selected_choices': [choice_id]}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        attempt.refresh_from_db()
        self.assertEqual(attempt.answers_so_far, {str(question_id): [choice_id]})
        # No LevelAssessmentAnswer exists yet — that would leak correct_choice_ids
        # to the frontend mid-exam (see LevelAssessmentAnswerSerializer).
        self.assertEqual(attempt.answers.count(), 0)
        # And the attempt's own serialized `answers` list stays empty too.
        self.assertEqual(response.data['answers'], [])

    def test_advance_must_be_sequential(self):
        attempt = self.start_attempt()
        response = self.client.post(
            f'/api/level-attempts/{attempt.id}/advance/', {'current_question_index': 2}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_advance_resets_the_timer_segment_under_per_question_timing(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.PER_QUESTION, seconds_per_question=60,
        )
        attempt = self.start_attempt()
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=45),
        )

        response = self.client.post(
            f'/api/level-attempts/{attempt.id}/advance/', {'current_question_index': 1}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['current_question_index'], 1)
        # Freshly reset — nowhere near the 15s that would remain without a reset.
        self.assertGreaterEqual(response.data['remaining_seconds'], 59)

    def test_timeout_advance_succeeds_when_server_already_moved_to_requested_question(self):
        """The timeout UI and server clock can expire at the same time."""
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.PER_QUESTION, seconds_per_question=60,
        )
        attempt = self.start_attempt()
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=61),
        )

        response = self.client.post(
            f'/api/level-attempts/{attempt.id}/advance/', {'current_question_index': 1}, format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['current_question_index'], 1)
        self.assertIsNone(response.data['submitted_at'])

    def test_advance_does_not_reset_the_timer_under_fixed_total_timing(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.FIXED_TOTAL, total_exam_minutes=10,
        )
        attempt = self.start_attempt()
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=120),
        )

        response = self.client.post(
            f'/api/level-attempts/{attempt.id}/advance/', {'current_question_index': 1}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        # 600s total - 120s already elapsed = ~480s left, NOT reset to ~600.
        self.assertLessEqual(response.data['remaining_seconds'], 481)
        self.assertGreaterEqual(response.data['remaining_seconds'], 470)

    def test_resuming_after_one_questions_time_fully_elapsed_advances_exactly_one_question(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.PER_QUESTION, seconds_per_question=60,
        )
        attempt = self.start_attempt()
        # Simulate: away long enough for question 0's 60s to fully elapse,
        # plus 10s into question 1's own countdown.
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=70),
        )

        response = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['submitted_at'])
        self.assertEqual(response.data['current_question_index'], 1)
        self.assertGreaterEqual(response.data['remaining_seconds'], 48)
        self.assertLessEqual(response.data['remaining_seconds'], 50)

    def test_resuming_after_multiple_questions_time_elapsed_cascades_through_all_of_them(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.PER_QUESTION, seconds_per_question=30,
        )
        attempt = self.start_attempt()
        # Away long enough for questions 0 and 1's 30s each (60s) to fully
        # elapse, landing 5s into question 2 — the last one.
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=65),
        )

        response = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertIsNone(response.data['submitted_at'])
        self.assertEqual(response.data['current_question_index'], 2)
        self.assertGreaterEqual(response.data['remaining_seconds'], 24)
        self.assertLessEqual(response.data['remaining_seconds'], 26)

    def test_resuming_after_the_last_questions_time_elapsed_auto_submits_with_zero_marks_for_the_rest(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.PER_QUESTION, seconds_per_question=30,
        )
        attempt = self.start_attempt()
        first_question_id = attempt.questions_drawn[0]
        first_correct_choice = self.correct_choices[self.questions.index(LevelQuestion.objects.get(id=first_question_id))]

        # Answer question 0 correctly before "leaving" ...
        self.client.post(
            f'/api/level-attempts/{attempt.id}/save-answer/',
            {'question': first_question_id, 'selected_choices': [first_correct_choice.id]}, format='json',
        )
        # ... then simulate being away long enough for all three 30s
        # questions (90s) to fully elapse.
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=95),
        )

        response = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data['submitted_at'])
        self.assertEqual(response.data['remaining_seconds'], 0)

        answers_by_question = {a['question']: a for a in response.data['answers']}
        self.assertTrue(answers_by_question[first_question_id]['is_correct'])
        self.assertFalse(answers_by_question[first_question_id]['is_unanswered'])
        for question_id in attempt.questions_drawn[1:]:
            self.assertEqual(answers_by_question[question_id]['selected_choices'], [])
            self.assertFalse(answers_by_question[question_id]['is_correct'])
            self.assertTrue(answers_by_question[question_id]['is_unanswered'])

        # A second fetch of an already-submitted attempt is a pure read —
        # no re-grading, no error.
        second_response = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertEqual(second_response.data['score_percent'], response.data['score_percent'])

    def test_resuming_under_fixed_total_with_time_still_left_does_not_submit(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.FIXED_TOTAL, total_exam_minutes=10,
        )
        attempt = self.start_attempt()
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=200),
        )

        response = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertIsNone(response.data['submitted_at'])
        self.assertEqual(response.data['current_question_index'], 0)  # FIXED_TOTAL never auto-advances position
        self.assertGreaterEqual(response.data['remaining_seconds'], 395)
        self.assertLessEqual(response.data['remaining_seconds'], 401)

    def test_resuming_under_fixed_total_after_time_fully_elapsed_auto_submits(self):
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.FIXED_TOTAL, total_exam_minutes=5,
        )
        attempt = self.start_attempt()
        second_question_id = attempt.questions_drawn[1]
        second_correct_choice = self.correct_choices[self.questions.index(LevelQuestion.objects.get(id=second_question_id))]
        self.client.post(
            f'/api/level-attempts/{attempt.id}/save-answer/',
            {'question': second_question_id, 'selected_choices': [second_correct_choice.id]}, format='json',
        )
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=301),
        )

        response = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertIsNotNone(response.data['submitted_at'])
        answers_by_question = {a['question']: a for a in response.data['answers']}
        self.assertTrue(answers_by_question[second_question_id]['is_correct'])
        for question_id in attempt.questions_drawn:
            if question_id != second_question_id:
                self.assertEqual(answers_by_question[question_id]['selected_choices'], [])

    def test_resume_survives_a_simulated_browser_crash_end_to_end(self):
        """The scenario from the task's own test plan: start, answer one
        question, "close the browser" (simulated by jumping the stored
        timestamp back), then fetch again as if reopening the app — same
        attempt, same question, correctly reduced time, not a fresh attempt."""
        OrganizationSettings.objects.filter(organization=self.org).update(
            timing_mode=OrganizationSettings.TimingMode.PER_QUESTION, seconds_per_question=120,
        )
        attempt = self.start_attempt()
        first_question_id = attempt.questions_drawn[0]
        first_correct_choice = self.correct_choices[self.questions.index(LevelQuestion.objects.get(id=first_question_id))]
        self.client.post(
            f'/api/level-attempts/{attempt.id}/save-answer/',
            {'question': first_question_id, 'selected_choices': [first_correct_choice.id]}, format='json',
        )

        # "Close the browser" for a known interval well short of a timeout.
        LevelAssessmentAttempt.objects.filter(id=attempt.id).update(
            timer_segment_started_at=timezone.now() - timedelta(seconds=30),
        )

        # "Reopen the app" — my-assessment-level says IN_PROGRESS with this
        # same attempt id, and fetching it resumes at the same question.
        status_response = self.client.get('/api/my-assessment-level/')
        self.assertEqual(status_response.data['status'], 'IN_PROGRESS')
        self.assertEqual(status_response.data['open_attempt_id'], attempt.id)

        resumed = self.client.get(f'/api/level-attempts/{attempt.id}/')
        self.assertEqual(resumed.data['current_question_index'], 0)
        self.assertEqual(resumed.data['answers_so_far'], {str(first_question_id): [first_correct_choice.id]})
        self.assertGreaterEqual(resumed.data['remaining_seconds'], 89)
        self.assertLessEqual(resumed.data['remaining_seconds'], 91)


class LevelAssessmentBadgeTests(TestCase):
    """
    gamification.services.award_badges_for_level_assessment_attempt — the
    five level-assessment-specific achievement conditions, exercised directly
    against manually-built attempts/answers (rather than the random-draw
    service) so each scenario's exact sequence/history is under test control.
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Acme Bank', slug='acme-bank-badges')
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=5,
        )
        question_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        self.questions = []
        for i in range(5):
            question = LevelQuestion.objects.create(
                question_set=question_set, question_text=f'Q{i}?',
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE, marks=1,
            )
            LevelChoice.objects.create(question=question, choice_text='Correct', is_correct=True)
            LevelChoice.objects.create(question=question, choice_text='Wrong', is_correct=False)
            self.questions.append(question)

    def make_user(self, email, branch_department=''):
        return User.objects.create_user(
            email=email, password='pw', role=User.Role.LEARNER, organization=self.org,
            assessment_level=User.AssessmentLevel.OFFICER, branch_department=branch_department,
        )

    def make_attempt(self, user, correctness, passed, questions_drawn=None):
        """`correctness` is a list of bools in drawn order, one per question in self.questions[:len(correctness)]."""
        questions = questions_drawn or self.questions[: len(correctness)]
        attempt = LevelAssessmentAttempt.objects.create(
            user=user, assessment_level=self.level, questions_drawn=[q.id for q in questions],
            submitted_at=timezone.now(), passed=passed,
            score_percent=Decimal('100.00') if all(correctness) else Decimal('40.00'),
        )
        for question, is_correct in zip(questions, correctness):
            LevelAssessmentAnswer.objects.create(attempt=attempt, question=question, is_correct=is_correct)
        return attempt

    def earned_keys(self, user):
        return set(UserBadge.objects.filter(user=user).values_list('badge__key', flat=True))

    # --- First Strike ---

    def test_first_strike_awarded_on_first_attempt_with_a_correct_answer(self):
        user = self.make_user('a@example.com')
        attempt = self.make_attempt(user, [True, False], passed=False)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertIn('first_strike', self.earned_keys(user))

    def test_first_strike_not_awarded_if_first_attempt_all_wrong(self):
        user = self.make_user('b@example.com')
        attempt = self.make_attempt(user, [False, False], passed=False)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertNotIn('first_strike', self.earned_keys(user))

    def test_first_strike_not_awarded_on_a_later_attempt(self):
        user = self.make_user('c@example.com')
        self.make_attempt(user, [False, False], passed=False)  # first attempt, all wrong
        second_attempt = self.make_attempt(user, [True, True], passed=False)  # second attempt, correct

        award_badges_for_level_assessment_attempt(second_attempt)

        self.assertNotIn('first_strike', self.earned_keys(user))

    # --- Hat Trick ---

    def test_hat_trick_awarded_for_three_consecutive_correct_in_drawn_order(self):
        user = self.make_user('d@example.com')
        attempt = self.make_attempt(user, [True, True, True, False, False], passed=False)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertIn('hat_trick', self.earned_keys(user))

    def test_hat_trick_awarded_for_a_trailing_streak(self):
        user = self.make_user('e@example.com')
        attempt = self.make_attempt(user, [True, False, True, True, True], passed=False)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertIn('hat_trick', self.earned_keys(user))

    def test_hat_trick_not_awarded_without_three_in_a_row(self):
        user = self.make_user('f@example.com')
        attempt = self.make_attempt(user, [True, True, False, True, True], passed=False)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertNotIn('hat_trick', self.earned_keys(user))

    # --- Perfect Score ---

    def test_perfect_score_awarded_for_100_percent_level_assessment(self):
        user = self.make_user('g@example.com')
        attempt = self.make_attempt(user, [True] * 5, passed=True)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertIn('perfect_score', self.earned_keys(user))

    def test_perfect_score_not_awarded_below_100_percent(self):
        user = self.make_user('h@example.com')
        attempt = self.make_attempt(user, [True, True, True, True, False], passed=True)
        attempt.score_percent = Decimal('80.00')
        attempt.save()

        award_badges_for_level_assessment_attempt(attempt)

        self.assertNotIn('perfect_score', self.earned_keys(user))

    # --- Comeback ---

    def test_comeback_awarded_after_a_prior_failed_attempt_at_the_same_level(self):
        user = self.make_user('i@example.com')
        self.make_attempt(user, [False, False], passed=False)
        second_attempt = self.make_attempt(user, [True, True], passed=True)

        award_badges_for_level_assessment_attempt(second_attempt)

        self.assertIn('comeback', self.earned_keys(user))

    def test_comeback_not_awarded_when_first_attempt_already_passed(self):
        user = self.make_user('j@example.com')
        attempt = self.make_attempt(user, [True, True], passed=True)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertNotIn('comeback', self.earned_keys(user))

    def test_comeback_not_awarded_when_the_retake_also_fails(self):
        user = self.make_user('k@example.com')
        self.make_attempt(user, [False, False], passed=False)
        second_attempt = self.make_attempt(user, [False, False], passed=False)

        award_badges_for_level_assessment_attempt(second_attempt)

        self.assertNotIn('comeback', self.earned_keys(user))

    # --- Branch Pride ---

    def test_branch_pride_awarded_to_first_passer_in_a_branch(self):
        user = self.make_user('l@example.com', branch_department='Head Office')
        attempt = self.make_attempt(user, [True, True], passed=True)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertIn('branch_pride', self.earned_keys(user))

    def test_branch_pride_not_awarded_to_second_passer_in_the_same_branch(self):
        first_user = self.make_user('m@example.com', branch_department='Head Office')
        first_attempt = self.make_attempt(first_user, [True, True], passed=True)
        award_badges_for_level_assessment_attempt(first_attempt)

        second_user = self.make_user('n@example.com', branch_department='Head Office')
        second_attempt = self.make_attempt(second_user, [True, True], passed=True)
        award_badges_for_level_assessment_attempt(second_attempt)

        self.assertNotIn('branch_pride', self.earned_keys(second_user))

    def test_branch_pride_awarded_independently_per_branch(self):
        first_user = self.make_user('o@example.com', branch_department='Head Office')
        award_badges_for_level_assessment_attempt(self.make_attempt(first_user, [True, True], passed=True))

        other_branch_user = self.make_user('p@example.com', branch_department='Pokhara Branch')
        other_attempt = self.make_attempt(other_branch_user, [True, True], passed=True)
        award_badges_for_level_assessment_attempt(other_attempt)

        self.assertIn('branch_pride', self.earned_keys(other_branch_user))

    def test_branch_pride_not_awarded_without_a_branch_department(self):
        user = self.make_user('q@example.com', branch_department='')
        attempt = self.make_attempt(user, [True, True], passed=True)

        award_badges_for_level_assessment_attempt(attempt)

        self.assertNotIn('branch_pride', self.earned_keys(user))

    # --- Idempotency / already-earned ---

    def test_badge_not_re_awarded_if_already_earned(self):
        user = self.make_user('r@example.com')
        badge = Badge.objects.get(key='first_strike')
        UserBadge.objects.create(user=user, badge=badge)

        attempt = self.make_attempt(user, [True, True], passed=False)
        award_badges_for_level_assessment_attempt(attempt)

        self.assertEqual(UserBadge.objects.filter(user=user, badge=badge).count(), 1)


class LevelAssessmentBadgeIntegrationTests(BaseAPITestCase):
    """Confirms the submit endpoint actually wires up badge awarding, not just the service function in isolation."""

    def test_submitting_a_perfect_first_attempt_awards_first_strike_and_perfect_score(self):
        level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=1,
        )
        question_set = QuestionSet.objects.create(assessment_level=level, label='Set 1')
        question = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q1?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        correct_choice = LevelChoice.objects.create(question=question, choice_text='Correct', is_correct=True)
        LevelChoice.objects.create(question=question, choice_text='Wrong', is_correct=False)

        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save()
        self.auth_as(self.learner)

        start_response = self.client.post('/api/level-attempts/start/')
        attempt_id = start_response.data['id']

        submit_response = self.client.post(
            f'/api/level-attempts/{attempt_id}/submit/',
            {'answers': [{'question': question.id, 'selected_choices': [correct_choice.id]}]},
            format='json',
        )

        self.assertEqual(submit_response.status_code, 200)
        earned = set(UserBadge.objects.filter(user=self.learner).values_list('badge__key', flat=True))
        self.assertIn('first_strike', earned)
        self.assertIn('perfect_score', earned)


class LeaderboardLevelAssessmentPointsTests(TestCase):
    """
    gamification.services.recalculate_leaderboard_entry's level-assessment
    contribution — exercised directly against manually-built attempts so the
    exact pass/fail/retake/score history is under test control. The bonus is
    round(LEVEL_ASSESSMENT_PASS_POINTS * score_percent / 100) for each
    distinct passed level (that level's own best PASSING score if passed
    more than once) — not a flat award for merely passing.
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Acme Bank', slug='acme-bank-points')
        self.user = User.objects.create_user(
            email='points@example.com', password='pw', role=User.Role.LEARNER, organization=self.org,
        )
        self.level_a = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, questions_per_attempt=1,
        )
        self.level_b = configure_assessment_level(
            self.org, User.AssessmentLevel.MANAGEMENT, questions_per_attempt=1,
        )

    def make_attempt(self, level, passed, score_percent=Decimal('0')):
        return LevelAssessmentAttempt.objects.create(
            user=self.user, assessment_level=level, questions_drawn=[], submitted_at=timezone.now(),
            passed=passed, score_percent=score_percent,
        )

    def test_max_achievable_level_assessment_bonus_exceeds_a_single_course_completion(self):
        # LEVEL_ASSESSMENT_PASS_POINTS is the bonus at a perfect 100% score —
        # the task's explicit requirement is that a level assessment CAN be
        # worth more than an ordinary course completion, reflecting its
        # higher-stakes status — not that a bare pass always is, now that
        # the bonus scales with score.
        self.assertGreater(LEVEL_ASSESSMENT_PASS_POINTS, COURSE_COMPLETION_POINTS)

    def test_passed_level_assessment_awards_points_scaled_by_its_score(self):
        self.make_attempt(self.level_a, passed=True, score_percent=Decimal('80'))

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, round(LEVEL_ASSESSMENT_PASS_POINTS * Decimal('0.8')))
        self.assertEqual(entry.level_assessments_passed_count, 1)

    def test_perfect_score_awards_the_full_configured_amount(self):
        self.make_attempt(self.level_a, passed=True, score_percent=Decimal('100'))

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, LEVEL_ASSESSMENT_PASS_POINTS)

    def test_failed_attempt_awards_no_points_regardless_of_score(self):
        self.make_attempt(self.level_a, passed=False, score_percent=Decimal('65'))

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, 0)
        self.assertEqual(entry.level_assessments_passed_count, 0)

    def test_retake_uses_the_best_passing_score_not_the_latest_attempt(self):
        self.make_attempt(self.level_a, passed=False, score_percent=Decimal('40'))
        self.make_attempt(self.level_a, passed=True, score_percent=Decimal('90'))
        self.make_attempt(self.level_a, passed=True, score_percent=Decimal('75'))  # retake, scored lower

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, round(LEVEL_ASSESSMENT_PASS_POINTS * Decimal('0.9')))
        self.assertEqual(entry.level_assessments_passed_count, 1)

    def test_passing_two_distinct_levels_sums_each_ones_own_scaled_bonus(self):
        self.make_attempt(self.level_a, passed=True, score_percent=Decimal('80'))
        self.make_attempt(self.level_b, passed=True, score_percent=Decimal('60'))

        entry = recalculate_leaderboard_entry(self.user)

        expected = round(LEVEL_ASSESSMENT_PASS_POINTS * Decimal('0.8')) + round(
            LEVEL_ASSESSMENT_PASS_POINTS * Decimal('0.6')
        )
        self.assertEqual(entry.total_points, expected)
        self.assertEqual(entry.level_assessments_passed_count, 2)

    def test_combines_with_path_scoped_course_completion_points(self):
        # path_order is required for a course to contribute points at all —
        # see LeaderboardPathScopedCoursePointsTests.
        course = Course.objects.create(
            title='Compliance 101', slug='compliance-101-points', organization=self.org,
            content_owner=Course.ContentOwner.ORGANIZATION, path_order=1,
        )
        Enrollment.objects.create(user=self.user, course=course, status=Enrollment.Status.COMPLETED)
        self.make_attempt(self.level_a, passed=True, score_percent=Decimal('100'))

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, COURSE_COMPLETION_POINTS + LEVEL_ASSESSMENT_PASS_POINTS)


class LeaderboardPathScopedCoursePointsTests(TestCase):
    """
    gamification.services.recalculate_leaderboard_entry's course-completion
    points only count a course actually in the learner's own assigned
    Learning Path: path_order must be set, and minimum_assessment_level
    must be null (Foundation) or at-or-below the learner's own
    assessment_level (courses.learning_path.tier_rank — an "at or below"
    ordinal comparison, deliberately looser than the exact single-tier
    match build_learning_path uses for path membership/gating).
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Acme Bank', slug='acme-bank-path-points')
        self.user = User.objects.create_user(
            email='pathpoints@example.com', password='pw', role=User.Role.LEARNER, organization=self.org,
        )

    def _make_course(self, slug, path_order=None, minimum_assessment_level=None):
        return Course.objects.create(
            title=slug, slug=slug, organization=self.org, content_owner=Course.ContentOwner.ORGANIZATION,
            path_order=path_order, minimum_assessment_level=minimum_assessment_level,
        )

    def test_course_with_no_path_order_contributes_nothing(self):
        course = self._make_course('no-path-order')
        Enrollment.objects.create(user=self.user, course=course, status=Enrollment.Status.COMPLETED)

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, 0)

    def test_foundation_course_always_counts(self):
        course = self._make_course('foundation-1', path_order=1)
        Enrollment.objects.create(user=self.user, course=course, status=Enrollment.Status.COMPLETED)

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, COURSE_COMPLETION_POINTS)

    def test_course_matching_the_users_own_tier_counts(self):
        self.user.assessment_level = User.AssessmentLevel.OFFICER
        self.user.save(update_fields=['assessment_level'])
        course = self._make_course('officer-1', path_order=2, minimum_assessment_level=User.AssessmentLevel.OFFICER)
        Enrollment.objects.create(user=self.user, course=course, status=Enrollment.Status.COMPLETED)

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, COURSE_COMPLETION_POINTS)

    def test_course_above_the_users_own_tier_contributes_nothing(self):
        # Ordinarily unreachable via normal path gating (a learner can't
        # complete a tier above their own), but exercised directly to prove
        # the leaderboard's own scoping rule holds regardless.
        self.user.assessment_level = User.AssessmentLevel.ASSISTANT_SUPERVISOR
        self.user.save(update_fields=['assessment_level'])
        course = self._make_course('officer-1', path_order=2, minimum_assessment_level=User.AssessmentLevel.OFFICER)
        Enrollment.objects.create(user=self.user, course=course, status=Enrollment.Status.COMPLETED)

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, 0)

    def test_course_below_the_users_own_tier_still_counts(self):
        # A Senior Management learner's previously-completed Officer-tier
        # course counts — tier_rank is "at or below", not an exact match.
        self.user.assessment_level = User.AssessmentLevel.SENIOR_MANAGEMENT
        self.user.save(update_fields=['assessment_level'])
        course = self._make_course('officer-1', path_order=2, minimum_assessment_level=User.AssessmentLevel.OFFICER)
        Enrollment.objects.create(user=self.user, course=course, status=Enrollment.Status.COMPLETED)

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, COURSE_COMPLETION_POINTS)

    def test_courses_completed_count_is_not_path_scoped(self):
        # A separate stat from points — feeds the first_course_complete/
        # five_courses_complete badges — deliberately counts every
        # completed course regardless of path membership.
        course = self._make_course('no-path-order-2')
        Enrollment.objects.create(user=self.user, course=course, status=Enrollment.Status.COMPLETED)

        entry = recalculate_leaderboard_entry(self.user)

        self.assertEqual(entry.total_points, 0)
        self.assertEqual(entry.courses_completed_count, 1)

    def test_full_hand_calculation_matches_a_realistic_multi_course_scenario(self):
        # One path course, one non-path (legacy/ad-hoc) course, and a passed
        # level assessment at a partial score — hand-computed expected total.
        self.user.assessment_level = User.AssessmentLevel.OFFICER
        self.user.save(update_fields=['assessment_level'])

        path_course = self._make_course('path-course', path_order=1)
        Enrollment.objects.create(user=self.user, course=path_course, status=Enrollment.Status.COMPLETED)

        outside_path_course = self._make_course('outside-path-course')  # no path_order
        Enrollment.objects.create(user=self.user, course=outside_path_course, status=Enrollment.Status.COMPLETED)

        level = configure_assessment_level(self.org, User.AssessmentLevel.OFFICER, questions_per_attempt=1)
        LevelAssessmentAttempt.objects.create(
            user=self.user, assessment_level=level, questions_drawn=[], submitted_at=timezone.now(),
            passed=True, score_percent=Decimal('80'),
        )

        entry = recalculate_leaderboard_entry(self.user)

        # path_course: 100 + 0 quiz bonus (no quizzes attempted) = 100.
        # outside_path_course: excluded entirely (no path_order) = 0.
        # Level assessment: round(150 * 0.8) = 120.
        expected_total = COURSE_COMPLETION_POINTS + round(LEVEL_ASSESSMENT_PASS_POINTS * Decimal('0.8'))
        self.assertEqual(expected_total, 220)
        self.assertEqual(entry.total_points, expected_total)
        # courses_completed_count stays unscoped (both completions count).
        self.assertEqual(entry.courses_completed_count, 2)


class LeaderboardLevelAssessmentIntegrationTests(BaseAPITestCase):
    """Confirms level assessment points flow through the real submit endpoint, and that the
    leaderboard stays organization-scoped (Phase 25's original hard requirement) once they do."""

    def setUp(self):
        super().setUp()
        self.level = configure_assessment_level(
            self.org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=1,
        )
        question_set = QuestionSet.objects.create(assessment_level=self.level, label='Set 1')
        self.question = LevelQuestion.objects.create(
            question_set=question_set, question_text='Q1?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        self.correct_choice = LevelChoice.objects.create(question=self.question, choice_text='Correct', is_correct=True)
        LevelChoice.objects.create(question=self.question, choice_text='Wrong', is_correct=False)

        self.learner.assessment_level = User.AssessmentLevel.OFFICER
        self.learner.save()

    def test_passing_updates_leaderboard_points_through_the_submit_endpoint(self):
        self.auth_as(self.learner)
        start_response = self.client.post('/api/level-attempts/start/')
        attempt_id = start_response.data['id']

        submit_response = self.client.post(
            f'/api/level-attempts/{attempt_id}/submit/',
            {'answers': [{'question': self.question.id, 'selected_choices': [self.correct_choice.id]}]},
            format='json',
        )

        self.assertEqual(submit_response.status_code, 200)
        entry = LeaderboardEntry.objects.get(user=self.learner)
        self.assertEqual(entry.total_points, LEVEL_ASSESSMENT_PASS_POINTS)
        self.assertEqual(entry.level_assessments_passed_count, 1)

    def test_leaderboard_endpoint_stays_organization_scoped_after_a_level_assessment_pass(self):
        # A learner in a *different* organization passes their own level
        # assessment — its points must never surface in self.org's leaderboard.
        other_level = configure_assessment_level(
            self.other_org, User.AssessmentLevel.OFFICER, pass_threshold=50, questions_per_attempt=1,
        )
        other_question_set = QuestionSet.objects.create(assessment_level=other_level, label='Set 1')
        other_question = LevelQuestion.objects.create(
            question_set=other_question_set, question_text='Q?', question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
            marks=1,
        )
        other_correct = LevelChoice.objects.create(question=other_question, choice_text='Correct', is_correct=True)
        LevelChoice.objects.create(question=other_question, choice_text='Wrong', is_correct=False)

        self.other_org_learner.assessment_level = User.AssessmentLevel.OFFICER
        self.other_org_learner.save()
        self.auth_as(self.other_org_learner)
        start_response = self.client.post('/api/level-attempts/start/')
        self.client.post(
            f'/api/level-attempts/{start_response.data["id"]}/submit/',
            {'answers': [{'question': other_question.id, 'selected_choices': [other_correct.id]}]},
            format='json',
        )

        self.auth_as(self.learner)
        response = self.client.get('/api/leaderboard/')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.other_org_learner.id, [row['user_id'] for row in response.data])
        # And confirm the other org's entry really was created with points —
        # this is a scoping check, not a "nothing happened" false negative.
        other_entry = LeaderboardEntry.objects.get(user=self.other_org_learner)
        self.assertEqual(other_entry.total_points, LEVEL_ASSESSMENT_PASS_POINTS)


class ResourceFlowTests(BaseAPITestCase):
    def test_org_admin_can_upload_pdf_and_it_appears_for_same_org_learner_only(self):
        self.auth_as(self.org_admin)
        response = self.client.post('/api/resources/', {
            'title': 'AML Policy', 'description': 'Annual policy document', 'file': make_test_pdf_upload(),
        }, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['title'], 'AML Policy')
        self.assertNotIn('file', response.data)  # never echoed back — see ResourceSerializer
        resource_id = response.data['id']
        self.assertEqual(Resource.objects.get(pk=resource_id).organization_id, self.org.id)

        # Same-org learner sees it.
        self.auth_as(self.learner)
        list_response = self.client.get('/api/resources/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([r['id'] for r in list_response.data], [resource_id])

        # A different organization's learner and admin do not.
        self.auth_as(self.other_org_learner)
        self.assertEqual(self.client.get('/api/resources/').data, [])
        self.assertEqual(self.client.get(f'/api/resources/{resource_id}/').status_code, 404)

        other_org_admin = User.objects.create_user(
            email='other-orgadmin@example.com', password='pass12345',
            role=User.Role.ORG_ADMIN, organization=self.other_org,
        )
        self.auth_as(other_org_admin)
        self.assertEqual(self.client.get('/api/resources/').data, [])

    def test_non_pdf_upload_rejected_by_extension_and_content_type(self):
        self.auth_as(self.org_admin)

        pptx_upload = SimpleUploadedFile(
            'slides.pptx', b'not really a pdf',
            content_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        )
        response = self.client.post('/api/resources/', {
            'title': 'Bad Upload', 'file': pptx_upload,
        }, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertIn('file', response.data)
        self.assertEqual(Resource.objects.count(), 0)

        docx_upload = SimpleUploadedFile(
            'doc.docx', b'not really a pdf',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        response = self.client.post('/api/resources/', {
            'title': 'Bad Upload 2', 'file': docx_upload,
        }, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Resource.objects.count(), 0)

    def test_renamed_non_pdf_rejected_by_content_sniffing(self):
        # Right extension and content_type, but the bytes aren't a PDF — the
        # magic-number check in resources.validators.validate_pdf_content
        # must catch what the extension/content_type checks alone would miss.
        self.auth_as(self.org_admin)
        fake_pdf = SimpleUploadedFile('report.pdf', b'this is actually plain text', content_type='application/pdf')
        response = self.client.post('/api/resources/', {'title': 'Fake', 'file': fake_pdf}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Resource.objects.count(), 0)

    def test_oversized_pdf_rejected(self):
        self.auth_as(self.org_admin)
        oversized = make_test_pdf_upload(body=b'x' * (20 * 1024 * 1024 + 1))
        response = self.client.post('/api/resources/', {'title': 'Too Big', 'file': oversized}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Resource.objects.count(), 0)

    def test_learner_cannot_upload_or_delete(self):
        self.auth_as(self.learner)
        response = self.client.post('/api/resources/', {
            'title': 'Nope', 'file': make_test_pdf_upload(),
        }, format='multipart')
        self.assertEqual(response.status_code, 403)

        resource = Resource.objects.create(
            organization=self.org, title='Existing', file=make_test_pdf_upload(), uploaded_by=self.org_admin,
        )
        self.assertEqual(self.client.delete(f'/api/resources/{resource.id}/').status_code, 403)

    def test_org_admin_can_only_delete_their_own_upload(self):
        other_admin_same_org = User.objects.create_user(
            email='second-orgadmin@example.com', password='pass12345',
            role=User.Role.ORG_ADMIN, organization=self.org,
        )
        resource = Resource.objects.create(
            organization=self.org, title='Someone else\'s upload', file=make_test_pdf_upload(),
            uploaded_by=other_admin_same_org,
        )

        self.auth_as(self.org_admin)
        response = self.client.delete(f'/api/resources/{resource.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Resource.objects.filter(pk=resource.id).exists())

        own_resource = Resource.objects.create(
            organization=self.org, title='My upload', file=make_test_pdf_upload(), uploaded_by=self.org_admin,
        )
        response = self.client.delete(f'/api/resources/{own_resource.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Resource.objects.filter(pk=own_resource.id).exists())

    def test_platform_admin_can_delete_any_organization_resource(self):
        resource = Resource.objects.create(
            organization=self.org, title='Org doc', file=make_test_pdf_upload(), uploaded_by=self.org_admin,
        )
        self.auth_as(self.platform_admin)
        response = self.client.delete(f'/api/resources/{resource.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Resource.objects.filter(pk=resource.id).exists())

    def test_learner_can_stream_same_org_resource_but_not_other_org_resource(self):
        resource = Resource.objects.create(
            organization=self.org, title='Policy', file=make_test_pdf_upload(), uploaded_by=self.org_admin,
        )
        other_resource = Resource.objects.create(
            organization=self.other_org, title='Other Policy', file=make_test_pdf_upload(), uploaded_by=self.org_admin,
        )

        self.auth_as(self.learner)
        response = self.client.get(f'/api/resources/{resource.id}/stream/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Content-Disposition'], 'inline')

        # A direct URL/ID guess at another organization's resource is denied,
        # not just hidden from the list.
        denied = self.client.get(f'/api/resources/{other_resource.id}/stream/')
        self.assertEqual(denied.status_code, 404)

    def test_unauthenticated_request_denied(self):
        resource = Resource.objects.create(
            organization=self.org, title='Policy', file=make_test_pdf_upload(), uploaded_by=self.org_admin,
        )
        self.client.credentials()  # clear auth_as's bearer token
        self.assertEqual(self.client.get('/api/resources/').status_code, 401)
        self.assertEqual(self.client.get(f'/api/resources/{resource.id}/stream/').status_code, 401)
