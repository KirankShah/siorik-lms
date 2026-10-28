from datetime import datetime, time, timedelta, timezone
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from unittest.mock import patch

from accounts.models import Organization, User
from periodic_exams.models import PeriodicExamAttempt, PeriodicExamReminderDelivery
from periodic_exams.reminders import reminder_days_remaining, send_due_periodic_exam_reminders
from periodic_exams.services import ensure_current_cycle

from .test_phase2 import BEFORE_ALL_TEST_CYCLES, add_question, enable, set_joined


KATHMANDU_OFFSET = timezone(timedelta(hours=5, minutes=45))
CYCLE_NOW = datetime(2027, 4, 1, 12, tzinfo=timezone.utc)


def local_instant(value, at=time(12)):
    return datetime.combine(value, at, KATHMANDU_OFFSET).astimezone(timezone.utc)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PeriodicExamReminderTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Reminder Bank', slug='reminder-bank')
        self.settings = enable(self.organization, questions_per_exam=1)
        self.settings.reminders_enabled = True
        self.settings.reminder_days_before_end = [7]
        self.settings.save(update_fields=['reminders_enabled', 'reminder_days_before_end'])
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Reminder question')
        self.learners = {}
        for key in ('due', 'exempt', 'passed', 'exhausted', 'inactive', 'revoked'):
            learner = User.objects.create_user(
                email=f'{key}@example.com', password='Pass1234', role=User.Role.LEARNER,
                organization=self.organization, assessment_level=User.AssessmentLevel.OFFICER,
                first_name=key.title(),
            )
            set_joined(learner, BEFORE_ALL_TEST_CYCLES)
            self.learners[key] = learner
        self.learners['exempt'].reminder_exempt = True
        self.learners['exempt'].save(update_fields=['reminder_exempt'])
        self.cycle = ensure_current_cycle(self.organization, CYCLE_NOW)
        PeriodicExamAttempt.objects.create(
            participant=self.cycle.participants.get(learner=self.learners['due']),
            attempt_number=1, started_at=CYCLE_NOW, timer_segment_started_at=CYCLE_NOW,
        )
        PeriodicExamAttempt.objects.create(
            participant=self.cycle.participants.get(learner=self.learners['exempt']),
            attempt_number=1, started_at=CYCLE_NOW, timer_segment_started_at=CYCLE_NOW,
            submitted_at=CYCLE_NOW, score_percent=40, passed=False,
            submission_reason=PeriodicExamAttempt.SubmissionReason.LEARNER,
        )
        self.cycle.participants.filter(learner=self.learners['exempt']).update(
            attempts_used=1, best_score_percent=40, last_attempt_at=CYCLE_NOW,
        )
        self.cycle.participants.filter(learner=self.learners['passed']).update(passed_at=CYCLE_NOW)
        exhausted = self.cycle.participants.get(learner=self.learners['exhausted'])
        for number in (1, 2):
            PeriodicExamAttempt.objects.create(
                participant=exhausted, attempt_number=number,
                started_at=CYCLE_NOW, timer_segment_started_at=CYCLE_NOW,
                submitted_at=CYCLE_NOW, score_percent=40, passed=False,
                submission_reason=PeriodicExamAttempt.SubmissionReason.LEARNER,
            )
        self.cycle.participants.filter(pk=exhausted.pk).update(
            attempts_used=2, best_score_percent=40, last_attempt_at=CYCLE_NOW,
        )
        self.cycle.participants.filter(learner=self.learners['revoked']).update(revoked_at=CYCLE_NOW)
        self.learners['inactive'].is_active = False
        self.learners['inactive'].save(update_fields=['is_active'])
        self.due_now = local_instant(self.cycle.end_date_ad - timedelta(days=7))

    def test_activation_and_seven_day_messages_send_once_to_the_correct_audience(self):
        activation = send_due_periodic_exam_reminders(now=CYCLE_NOW)
        self.assertEqual((activation['activation_due'], activation['sent']), (4, 4))
        self.assertEqual(len(mail.outbox), 4)
        self.assertTrue(all('now active' in message.subject for message in mail.outbox))
        self.assertTrue(all(self.cycle.display_label in message.body for message in mail.outbox))

        due = send_due_periodic_exam_reminders(now=self.due_now)
        self.assertEqual((due['deadline_due'], due['sent'], due['duplicate']), (2, 2, 4))
        self.assertEqual(len(mail.outbox), 6)
        self.assertIn(str(self.cycle.end_date_ad), mail.outbox[-1].body)
        self.assertTrue(any('retake' in message.body.lower() for message in mail.outbox[-2:]))

        second = send_due_periodic_exam_reminders(now=self.due_now)
        self.assertEqual((second['sent'], second['duplicate']), (0, 6))
        self.assertEqual(len(mail.outbox), 6)
        self.assertEqual(PeriodicExamReminderDelivery.objects.filter(sent_at__isnull=False).count(), 6)
        self.learners['exempt'].refresh_from_db()
        self.assertTrue(self.learners['exempt'].reminder_exempt)

    def test_failure_is_recorded_and_retried(self):
        calls = []

        def fail_once(participant, days):
            calls.append(participant.id)
            if len(calls) == 1:
                raise RuntimeError('temporary mail failure')

        first = send_due_periodic_exam_reminders(now=CYCLE_NOW, email_sender=fail_once)
        self.assertEqual((first['failed'], first['sent']), (1, 3))
        failed = PeriodicExamReminderDelivery.objects.get(sent_at__isnull=True)
        self.assertEqual(failed.attempt_count, 1)
        self.assertIn('temporary mail failure', failed.last_error)

        second = send_due_periodic_exam_reminders(now=CYCLE_NOW, email_sender=fail_once)
        self.assertEqual((second['sent'], second['duplicate']), (1, 3))
        failed.refresh_from_db()
        self.assertEqual(failed.attempt_count, 2)
        self.assertIsNotNone(failed.sent_at)
        self.assertEqual(failed.last_error, '')

    def test_disabled_or_subscription_expired_organization_is_skipped(self):
        self.settings.enabled = False
        self.settings.save(update_fields=['enabled'])
        self.assertEqual(send_due_periodic_exam_reminders(now=self.due_now)['due'], 0)
        self.settings.enabled = True
        self.settings.save(update_fields=['enabled'])
        org_settings = self.organization.settings
        org_settings.subscription_start_date = self.due_now.date() - timedelta(days=10)
        org_settings.subscription_duration_days = 1
        org_settings.save(update_fields=['subscription_start_date', 'subscription_duration_days'])
        self.assertEqual(send_due_periodic_exam_reminders(now=self.due_now)['due'], 0)

    def test_fixed_deadline_replaces_cycle_snapshot_reminder_configuration(self):
        self.settings.reminders_enabled = False
        self.settings.save(update_fields=['reminders_enabled'])
        due = send_due_periodic_exam_reminders(now=self.due_now, dry_run=True)
        self.assertEqual(due['activation_due'], 4)
        self.assertEqual(due['deadline_due'], 2)
        next_day = self.due_now + timedelta(days=1)
        self.assertEqual(send_due_periodic_exam_reminders(now=next_day, dry_run=True)['deadline_due'], 0)
        self.cycle.reminders_enabled = False
        self.cycle.save(update_fields=['reminders_enabled'])
        self.assertEqual(send_due_periodic_exam_reminders(now=self.due_now, dry_run=True)['deadline_due'], 2)

    def test_command_dry_run_does_not_write_or_send(self):
        output = StringIO()
        # The command uses the real current time, so exercise its output contract
        # while the deterministic audience calculation is covered above.
        call_command('send_periodic_exam_reminders', '--dry-run', stdout=output)
        self.assertIn('Dry run:', output.getvalue())
        self.assertEqual(PeriodicExamReminderDelivery.objects.count(), 0)

    @patch(
        'org_settings.management.commands.send_inactivity_reminders.send_due_inactivity_reminders',
        return_value=[],
    )
    def test_existing_inactivity_command_is_still_independent(self, inactivity_service):
        output = StringIO()
        call_command('send_inactivity_reminders', stdout=output)
        inactivity_service.assert_called_once_with()
        self.assertIn('No organizations were due', output.getvalue())

    def test_kathmandu_day_boundary_for_cycle_crossing_bs_new_year(self):
        self.assertEqual((self.cycle.end_year_bs, self.cycle.end_month_bs), (2083, 12))
        due_date = self.cycle.end_date_ad - timedelta(days=7)
        before_midnight = datetime.combine(
            due_date - timedelta(days=1), time(18, 14, 59), timezone.utc
        )
        at_midnight = datetime.combine(
            due_date - timedelta(days=1), time(18, 15), timezone.utc
        )
        self.assertEqual(reminder_days_remaining(self.cycle, before_midnight), 8)
        self.assertEqual(reminder_days_remaining(self.cycle, at_midnight), 7)
