"""
End-to-end API flow tests for the LMS backend.

Run with:
    python manage.py test test_api_flows
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Organization, User
from assessments.models import Choice, Question, Quiz, QuizAttempt
from certificates.services import generate_certificate
from courses.models import Course, Enrollment, Lesson, Module


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
    def test_learner_sees_only_published_courses_in_own_org_or_platform(self):
        self.auth_as(self.learner)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertEqual(slugs, {'org-onboarding', 'platform-basics'})

    def test_org_admin_sees_unpublished_org_courses_plus_platform(self):
        self.auth_as(self.org_admin)
        slugs = {c['slug'] for c in self.client.get('/api/courses/').data}
        self.assertEqual(slugs, {'org-onboarding', 'org-draft', 'platform-basics'})

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
