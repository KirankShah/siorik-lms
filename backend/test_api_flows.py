"""
End-to-end API flow tests for the LMS backend.

Run with:
    python manage.py test test_api_flows
"""
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Organization, User
from assessments.models import Choice, Question, Quiz, QuizAttempt
from audit.models import AuditLog
from certificates.services import generate_certificate
from courses.models import Course, CourseAccess, Enrollment, Lesson, Module


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

        self.quiz = Quiz.objects.create(course=self.published_org_course, title='Final Exam', pass_percentage=50, max_attempts=2)
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

    def test_course_retrieve_lists_its_quizzes(self):
        self.auth_as(self.learner)
        response = self.client.get('/api/courses/org-onboarding/')
        self.assertEqual([q['id'] for q in response.data['quizzes']], [self.quiz.id])
        self.assertEqual(response.data['quizzes'][0]['title'], 'Final Exam')


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

    def test_issue_endpoint_rejects_when_quiz_not_passed(self):
        Enrollment.objects.create(
            user=self.learner, course=self.published_org_course,
            status=Enrollment.Status.COMPLETED,
        )
        self.auth_as(self.learner)
        response = self.client.post('/api/certificates/issue/', {'course': self.published_org_course.id})
        self.assertEqual(response.status_code, 400)

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
        quiz_response = self.client.post('/api/quizzes/', {
            'course': self.published_org_course.id, 'title': 'New Quiz', 'pass_percentage': 60,
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
        response = self.client.post('/api/quizzes/', {
            'course': self.published_org_course.id, 'title': 'Nope',
        })
        self.assertEqual(response.status_code, 403)

    def test_cannot_add_question_to_other_org_quiz(self):
        other_quiz = Quiz.objects.create(course=self.other_org_course, title='Other Quiz')
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
