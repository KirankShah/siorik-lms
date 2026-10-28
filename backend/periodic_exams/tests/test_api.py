from datetime import date, datetime, timedelta, timezone

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Organization, User
from levelassessments.models import LevelQuestion, QuestionSet
from periodic_exams.models import PeriodicExamSettings


class PeriodicExamApiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='One', slug='one')
        self.other_org = Organization.objects.create(name='Two', slug='two')
        self.platform = User.objects.create_user(email='platform@example.com', password='Pass1234', role=User.Role.PLATFORM_ADMIN)
        self.org_admin = User.objects.create_user(email='admin@example.com', password='Pass1234', role=User.Role.ORG_ADMIN, organization=self.org)
        self.other_admin = User.objects.create_user(email='other@example.com', password='Pass1234', role=User.Role.ORG_ADMIN, organization=self.other_org)
        self.learner = User.objects.create_user(email='learner@example.com', password='Pass1234', role=User.Role.LEARNER, organization=self.org)
        self.instructor = User.objects.create_user(email='teacher@example.com', password='Pass1234', role=User.Role.INSTRUCTOR, organization=self.org)
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_defaults_and_disabled_feature_expose_no_configuration(self):
        self.authenticate(self.org_admin)
        response = self.client.get('/api/periodic-exams/settings/')
        self.assertEqual(response.status_code, 404)
        availability = self.client.get('/api/periodic-exams/availability/')
        self.assertEqual(availability.json(), {'enabled': False})
        row = PeriodicExamSettings.objects.get(organization=self.org)
        self.assertEqual(row.questions_per_exam, 30)
        self.assertEqual(row.pass_mark_percent, 60)
        self.assertEqual(row.seconds_per_question, 60)
        self.assertEqual(row.max_attempts_per_cycle, 2)
        self.assertTrue(row.reminders_enabled)
        self.assertEqual(row.reminder_days_before_end, [7])

    def test_only_platform_admin_can_toggle(self):
        url = f'/api/periodic-exams/platform/organizations/{self.org.id}/'
        for denied in (self.org_admin, self.learner, self.instructor):
            self.authenticate(denied)
            self.assertEqual(self.client.patch(url, {'enabled': True}, format='json').status_code, 403)
        self.authenticate(self.platform)
        response = self.client.patch(url, {'enabled': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['enabled'])
        self.assertIsNotNone(response.json()['enabled_from'])

    def test_org_admin_cannot_edit_enabled_and_is_tenant_scoped(self):
        PeriodicExamSettings.objects.create(organization=self.org, enabled=True, enabled_from=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc))
        PeriodicExamSettings.objects.create(organization=self.other_org, enabled=True, questions_per_exam=77, enabled_from=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc))
        self.authenticate(self.org_admin)
        response = self.client.patch('/api/periodic-exams/settings/', {'enabled': False, 'questions_per_exam': 35}, format='json')
        self.assertEqual(response.status_code, 200)
        own = PeriodicExamSettings.objects.get(organization=self.org)
        other = PeriodicExamSettings.objects.get(organization=self.other_org)
        self.assertTrue(own.enabled)
        self.assertEqual(own.questions_per_exam, 35)
        self.assertEqual(other.questions_per_exam, 77)

    def test_settings_validation_and_role_denials(self):
        PeriodicExamSettings.objects.create(organization=self.org, enabled=True, enabled_from=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc))
        self.authenticate(self.org_admin)
        response = self.client.patch('/api/periodic-exams/settings/', {'seconds_per_question': 4, 'reminder_days_before_end': [2, 2]}, format='json')
        self.assertEqual(response.status_code, 400)
        for denied in (self.platform, self.learner, self.instructor):
            self.authenticate(denied)
            response = self.client.get('/api/periodic-exams/settings/')
            self.assertEqual(response.status_code, 403)

    def test_platform_list_is_platform_only_and_contains_all_orgs(self):
        own_level = self.org.assessment_levels.get(name=User.AssessmentLevel.OFFICER)
        own_set = QuestionSet.objects.create(assessment_level=own_level, label='Officer pool')
        LevelQuestion.objects.create(question_set=own_set, question_text='  Same   visible question  ')
        LevelQuestion.objects.create(question_set=own_set, question_text='same visible question')
        other_level = self.other_org.assessment_levels.get(name=User.AssessmentLevel.MANAGEMENT)
        other_set = QuestionSet.objects.create(assessment_level=other_level, label='Management pool')
        LevelQuestion.objects.create(question_set=other_set, question_text='Other tenant question')

        self.authenticate(self.platform)
        response = self.client.get('/api/periodic-exams/platform/organizations/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item['id'] for item in response.json()}, {self.org.id, self.other_org.id})
        by_org = {item['id']: item for item in response.json()}
        own_counts = {
            item['level']: item['question_count']
            for item in by_org[self.org.id]['periodic_exam_question_counts']
        }
        other_counts = {
            item['level']: item['question_count']
            for item in by_org[self.other_org.id]['periodic_exam_question_counts']
        }
        self.assertEqual(own_counts[User.AssessmentLevel.OFFICER], 1)
        self.assertEqual(other_counts[User.AssessmentLevel.OFFICER], 0)
        self.assertEqual(other_counts[User.AssessmentLevel.MANAGEMENT], 1)
        self.authenticate(self.org_admin)
        self.assertEqual(self.client.get('/api/periodic-exams/platform/organizations/').status_code, 403)

    def test_availability_hides_feature_from_ineligible_learner_and_instructor(self):
        PeriodicExamSettings.objects.create(
            organization=self.org,
            enabled=True,
            enabled_from=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
        )
        self.authenticate(self.learner)
        self.assertEqual(self.client.get('/api/periodic-exams/availability/').json(), {'enabled': False})
        self.authenticate(self.instructor)
        self.assertEqual(self.client.get('/api/periodic-exams/availability/').json(), {'enabled': False})
        self.authenticate(self.org_admin)
        self.assertTrue(self.client.get('/api/periodic-exams/availability/').json()['enabled'])

    def test_subscription_middleware_locks_tenant_settings_but_not_platform_toggle(self):
        PeriodicExamSettings.objects.create(
            organization=self.org,
            enabled=True,
            enabled_from=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
        )
        org_settings = self.org.settings
        org_settings.subscription_start_date = date.today() - timedelta(days=2)
        org_settings.subscription_duration_days = 1
        org_settings.org_admin_grace_period_days = 0
        org_settings.save(update_fields=[
            'subscription_start_date', 'subscription_duration_days', 'org_admin_grace_period_days',
        ])

        self.client.force_authenticate(user=None)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.org_admin).access_token}',
        )
        response = self.client.get('/api/periodic-exams/settings/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'subscription_expired')

        self.client.credentials()
        self.authenticate(self.platform)
        response = self.client.patch(
            f'/api/periodic-exams/platform/organizations/{self.org.id}/',
            {'enabled': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
