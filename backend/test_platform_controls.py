from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.core import mail
from django.utils import timezone

from accounts.models import User
from courses.models import Enrollment
from org_settings.models import OrganizationSettings
from org_settings.services import send_due_inactivity_reminders
from test_api_flows import BaseAPITestCase


class LearnerSeatCapTests(BaseAPITestCase):
    def _create_staff(self, email):
        return self.client.post('/api/staff/', {
            'name': 'Seat Test',
            'email': email,
            'assessment_level': 'Officer Level',
        }, format='json')

    def test_cap_blocks_add_frees_on_deactivate_and_blocks_reactivation(self):
        OrganizationSettings.objects.filter(organization=self.org).update(max_active_learners=3)
        self.auth_as(self.org_admin)

        self.assertEqual(self._create_staff('seat-two@acme.test').status_code, 201)
        third = self._create_staff('seat-three@acme.test')
        self.assertEqual(third.status_code, 201)

        blocked = self._create_staff('seat-four@acme.test')
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('active learner limit of 3', blocked.data['detail'])
        self.assertIn('Deactivate an existing learner to free a slot', blocked.data['detail'])

        self.client.post(f'/api/staff/{third.data["id"]}/deactivate/')
        replacement = self._create_staff('replacement@acme.test')
        self.assertEqual(replacement.status_code, 201, replacement.data)

        blocked_reactivation = self.client.post(f'/api/staff/{third.data["id"]}/reactivate/')
        self.assertEqual(blocked_reactivation.status_code, 400)
        self.assertIn('active learner limit of 3', blocked_reactivation.data['detail'])

    def test_platform_only_fields_are_hidden_and_not_editable_by_org_admin(self):
        settings_obj = self.org.settings
        self.auth_as(self.org_admin)
        response = self.client.get('/api/organization-settings/')
        self.assertNotIn('max_active_learners', response.data[0])
        self.assertNotIn('subscription_start_date', response.data[0])

        self.client.patch(
            f'/api/organization-settings/{settings_obj.id}/',
            {'max_active_learners': 1, 'subscription_start_date': '2026-01-01', 'subscription_duration_days': 1},
            format='json',
        )
        settings_obj.refresh_from_db()
        self.assertIsNone(settings_obj.max_active_learners)
        self.assertIsNone(settings_obj.subscription_start_date)


class SubscriptionAccessTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.settings_obj = self.org.settings
        self.settings_obj.subscription_start_date = timezone.localdate() - timedelta(days=2)
        self.settings_obj.subscription_duration_days = 1
        self.settings_obj.save()

    def test_login_succeeds_but_tenant_pages_lock_while_platform_admin_is_unaffected(self):
        for user in (self.org_admin, self.learner):
            self.client.credentials()
            login = self.client.post('/api/auth/login/', {'email': user.email, 'password': 'pass12345'})
            self.assertEqual(login.status_code, 200)
            self.auth_as(user)
            me = self.client.get('/api/auth/me/')
            self.assertEqual(me.status_code, 200)
            self.assertTrue(me.data['subscription_access_locked'])
            locked = self.client.get('/api/courses/')
            self.assertEqual(locked.status_code, 403)
            self.assertEqual(locked.json()['detail'], "Your organization's subscription has expired.")

        self.auth_as(self.platform_admin)
        self.assertEqual(self.client.get('/api/courses/').status_code, 200)
        self.assertFalse(self.client.get('/api/auth/me/').data['subscription_access_locked'])

    def test_org_admin_grace_restores_full_access_only_for_org_admin(self):
        self.auth_as(self.platform_admin)
        response = self.client.patch(
            f'/api/organization-settings/{self.settings_obj.id}/',
            {'org_admin_grace_period_days': 5},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.auth_as(self.org_admin)
        self.assertEqual(self.client.get('/api/courses/').status_code, 200)
        self.assertFalse(self.client.get('/api/auth/me/').data['subscription_access_locked'])

        self.auth_as(self.learner)
        self.assertEqual(self.client.get('/api/courses/').status_code, 403)
        self.assertTrue(self.client.get('/api/auth/me/').data['subscription_access_locked'])


class PathOverdueAndExemptionTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.published_org_course.path_order = 1
        self.published_org_course.save(update_fields=['path_order'])
        self.settings_obj = self.org.settings
        self.settings_obj.logged_in_inactive_reminder_enabled = False
        self.settings_obj.never_logged_in_reminder_enabled = False
        self.settings_obj.path_overdue_reminder_enabled = True
        self.settings_obj.path_overdue_months_after_enrollment = 2
        self.settings_obj.path_overdue_repeat_days = 7
        self.settings_obj.save()

        self.enrollment = Enrollment.objects.create(user=self.learner, course=self.published_org_course)
        User.objects.filter(pk=self.learner.pk).update(date_joined=timezone.now() - relativedelta(months=3))
        self.learner.refresh_from_db()

    def test_path_overdue_sends_and_repeats_per_learner_until_complete(self):
        summaries = send_due_inactivity_reminders()
        self.assertTrue(any(s['reminder_type'] == 'path_overdue' and s['recipient_count'] == 1 for s in summaries))
        self.assertEqual([message.to for message in mail.outbox], [[self.learner.email]])

        mail.outbox.clear()
        send_due_inactivity_reminders()
        self.assertEqual(len(mail.outbox), 0)

        self.learner.refresh_from_db()
        self.learner.path_overdue_reminder_last_sent_at = timezone.now() - timedelta(days=8)
        self.learner.save(update_fields=['path_overdue_reminder_last_sent_at'])
        send_due_inactivity_reminders()
        self.assertEqual([message.to for message in mail.outbox], [[self.learner.email]])

        mail.outbox.clear()
        self.enrollment.status = Enrollment.Status.COMPLETED
        self.enrollment.save(update_fields=['status'])
        self.learner.path_overdue_reminder_last_sent_at = timezone.now() - timedelta(days=8)
        self.learner.save(update_fields=['path_overdue_reminder_last_sent_at'])
        send_due_inactivity_reminders()
        self.assertEqual(len(mail.outbox), 0)

    def test_exemption_skips_all_reminder_types_but_not_reporting(self):
        self.learner.reminder_exempt = True
        self.learner.save(update_fields=['reminder_exempt'])
        non_exempt = User.objects.create_user(
            email='non-exempt@acme.test', password='pass12345',
            role=User.Role.LEARNER, organization=self.org,
        )
        Enrollment.objects.create(user=non_exempt, course=self.published_org_course)
        User.objects.filter(pk=non_exempt.pk).update(date_joined=timezone.now() - relativedelta(months=3))
        self.settings_obj.never_logged_in_reminder_enabled = True
        self.settings_obj.save(update_fields=['never_logged_in_reminder_enabled'])

        with self.assertLogs('org_settings.services', level='INFO') as logs:
            send_due_inactivity_reminders()
        self.assertFalse(any(message.to == [self.learner.email] for message in mail.outbox))
        self.assertTrue(any(message.to == [non_exempt.email] for message in mail.outbox))
        self.assertTrue(any('skipped due to exemption' in line.lower() for line in logs.output))

        # Change the same exempt learner into the other inactivity audience;
        # path-overdue still applies at the same time, and both remain skipped.
        mail.outbox.clear()
        self.learner.last_login = timezone.now()
        self.learner.save(update_fields=['last_login'])
        self.settings_obj.logged_in_inactive_reminder_enabled = True
        self.settings_obj.logged_in_inactive_last_sent_at = None
        self.settings_obj.save(update_fields=['logged_in_inactive_reminder_enabled', 'logged_in_inactive_last_sent_at'])
        with self.assertLogs('org_settings.services', level='INFO') as logs:
            send_due_inactivity_reminders()
        self.assertFalse(any(message.to == [self.learner.email] for message in mail.outbox))
        self.assertTrue(any('reminder_type=logged_in_inactive' in line for line in logs.output))
        self.assertTrue(any('reminder_type=path_overdue' in line for line in logs.output))

        # Exemption is email-only: the incomplete learner remains in the staff
        # report and is not represented as complete.
        self.auth_as(self.org_admin)
        today = timezone.localdate().isoformat()
        report = self.client.get('/api/reports/staff-training/', {'date_from': '2020-01-01', 'date_to': today})
        self.assertEqual(report.status_code, 200, report.data)
        email_index = report.data['headers'].index('Email Address')
        path_status_index = report.data['headers'].index('Course Path Completed (Pass/Fail)')
        row = next(row for row in report.data['rows'] if row[email_index] == self.learner.email)
        self.assertEqual(row[path_status_index], '')

