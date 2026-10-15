"""Regression tests for the independent review: same-cycle repeats, calendar
range failures, and abandoned attempts that never closed."""
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Organization, User
from periodic_exams.calendar import CalendarRangeError
from periodic_exams.models import (
    PeriodicExamAttempt,
    PeriodicExamCycle,
    PeriodicExamQuestionUsage,
    PeriodicExamSettings,
)
from periodic_exams.reminders import send_due_periodic_exam_reminders
from periodic_exams.reports import build_report_row, report_participants
from periodic_exams.services import (
    PeriodicExamError,
    advance_periodic_attempt,
    close_expired_periodic_attempts,
    ensure_current_cycle,
    periodic_exam_summary,
    save_periodic_answer,
    set_feature_enabled,
    start_periodic_exam_attempt,
    submit_periodic_attempt,
)

from .test_phase2 import NOW, add_question, enable
from .test_phase3 import configure, make_learner

# BS 2091 Poush: past the supported 2083-2090 calendar range.
OUT_OF_RANGE = datetime(2035, 1, 1, 6, tzinfo=timezone.utc)


def start(learner, *, now=NOW, seed=1):
    return start_periodic_exam_attempt(learner, now=now, rng=random.Random(seed))[0]


def complete_wrong(attempt, learner, *, now):
    total = attempt.paper_questions.count()
    for index in range(total - 1):
        advance_periodic_attempt(learner, attempt.id, current_question_index=index, now=now)
    return submit_periodic_attempt(learner, attempt.id, now=now)


class SameCycleNoRepeatTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Repeat Bank', slug='repeat-bank')
        configure(enable(self.organization, questions_per_exam=3), questions=3, attempts=3)
        for index in range(5):
            add_question(self.organization, User.AssessmentLevel.OFFICER, f'Repeat question {index}')
        self.learner = make_learner(self.organization, 'repeat@example.com')

    def usage_snapshot(self):
        return list(PeriodicExamQuestionUsage.objects.order_by('id').values_list('question_key', 'times_used'))

    def test_retake_is_refused_instead_of_repeating_a_current_cycle_question(self):
        first = start(self.learner)
        complete_wrong(first, self.learner, now=NOW + timedelta(seconds=1))
        usage_before = self.usage_snapshot()

        summary = periodic_exam_summary(self.learner, now=NOW + timedelta(minutes=1))
        self.assertFalse(summary['can_start'])
        self.assertEqual(summary['reason_code'], 'CYCLE_POOL_EXHAUSTED')

        with self.assertRaises(PeriodicExamError) as error:
            start(self.learner, now=NOW + timedelta(minutes=1), seed=2)
        self.assertEqual(error.exception.code, 'CYCLE_POOL_EXHAUSTED')
        self.assertEqual(PeriodicExamAttempt.objects.count(), 1)
        self.assertEqual(self.usage_snapshot(), usage_before)

    def test_retake_with_enough_fresh_questions_is_fully_disjoint(self):
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Repeat question 5')
        first = start(self.learner)
        complete_wrong(first, self.learner, now=NOW + timedelta(seconds=1))
        retake = start(self.learner, now=NOW + timedelta(minutes=1), seed=2)
        first_keys = set(first.paper_questions.values_list('cycle_question__normalized_text_hash', flat=True))
        retake_keys = set(retake.paper_questions.values_list('cycle_question__normalized_text_hash', flat=True))
        self.assertEqual(len(retake_keys), 3)
        self.assertTrue(first_keys.isdisjoint(retake_keys))


class CalendarRangeFailClosedTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Range Bank', slug='range-bank')
        self.settings = enable(self.organization, questions_per_exam=1)
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Range question')
        self.learner = make_learner(self.organization, 'range@example.com')

    def test_no_new_cycle_outside_supported_range(self):
        self.assertIsNone(ensure_current_cycle(self.organization, OUT_OF_RANGE))
        self.assertFalse(PeriodicExamCycle.objects.exists())

    def test_existing_cycle_covering_now_is_still_returned(self):
        cycle = ensure_current_cycle(self.organization, NOW)
        with patch('periodic_exams.services.period_for', side_effect=CalendarRangeError('out of range')):
            self.assertEqual(ensure_current_cycle(self.organization, NOW), cycle)

    def test_learner_endpoints_and_reminders_do_not_500(self):
        client = APIClient()
        client.force_authenticate(self.learner)
        with patch('django.utils.timezone.now', return_value=OUT_OF_RANGE):
            self.assertEqual(client.get('/api/periodic-exams/availability/').status_code, 200)
            summary = client.get('/api/periodic-exams/me/summary/')
            self.assertEqual(summary.status_code, 404)
            self.assertEqual(summary.data['code'], 'CYCLE_CLOSED')
            start_response = client.post('/api/periodic-exams/me/attempts/start/')
            self.assertEqual(start_response.status_code, 400)
            self.assertEqual(start_response.data['code'], 'CYCLE_CLOSED')
        result = send_due_periodic_exam_reminders(now=OUT_OF_RANGE, email_sender=lambda *args: None)
        self.assertEqual(result['due'], 0)

    def test_enabling_or_changing_frequency_outside_range_returns_409(self):
        PeriodicExamSettings.objects.filter(pk=self.settings.pk).update(enabled=False, enabled_from=None)
        with self.assertRaises(PeriodicExamError) as error:
            set_feature_enabled(self.organization, True, None, now=OUT_OF_RANGE)
        self.assertEqual(error.exception.code, 'CALENDAR_UNSUPPORTED')
        self.assertEqual(error.exception.status_code, 409)
        self.settings.refresh_from_db()
        self.assertFalse(self.settings.enabled)

        platform = User.objects.create_user(
            email='range-platform@example.com', password='Pass1234', role=User.Role.PLATFORM_ADMIN,
        )
        client = APIClient()
        client.force_authenticate(platform)
        with patch('django.utils.timezone.now', return_value=OUT_OF_RANGE):
            response = client.patch(
                f'/api/periodic-exams/platform/organizations/{self.organization.id}/',
                {'enabled': True}, format='json',
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'CALENDAR_UNSUPPORTED')

        PeriodicExamSettings.objects.filter(pk=self.settings.pk).update(enabled=True, enabled_from=NOW)
        admin = User.objects.create_user(
            email='range-admin@example.com', password='Pass1234', role=User.Role.ORG_ADMIN,
            organization=self.organization,
        )
        client.force_authenticate(admin)
        with patch('django.utils.timezone.now', return_value=OUT_OF_RANGE):
            response = client.patch('/api/periodic-exams/settings/', {'frequency': 'QUARTERLY'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'CALENDAR_UNSUPPORTED')


class AbandonedAttemptReconciliationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Abandon Bank', slug='abandon-bank')
        configure(enable(self.organization, questions_per_exam=3), questions=3, attempts=3, seconds=5)
        for index in range(9):
            add_question(self.organization, User.AssessmentLevel.OFFICER, f'Abandon question {index}')
        self.learner = make_learner(self.organization, 'abandon@example.com')
        self.attempt = start(self.learner)
        row = self.attempt.paper_questions.select_related('cycle_question').get(order=0)
        save_periodic_answer(
            self.learner, self.attempt.id, current_question_index=0,
            selected_option_keys=row.cycle_question.correct_option_keys, now=NOW + timedelta(seconds=1),
        )

    def test_attempt_with_time_left_is_not_touched(self):
        self.assertEqual(close_expired_periodic_attempts(now=NOW + timedelta(seconds=14)), 0)
        self.attempt.refresh_from_db()
        self.assertIsNone(self.attempt.submitted_at)
        self.assertEqual(self.attempt.current_question_index, 0)

    def test_expired_attempt_is_scored_and_reported_as_failed(self):
        self.assertEqual(close_expired_periodic_attempts(now=NOW + timedelta(days=3)), 1)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.submitted_at, NOW + timedelta(seconds=15))
        self.assertEqual(self.attempt.submission_reason, PeriodicExamAttempt.SubmissionReason.QUESTION_TIMEOUT)
        self.assertEqual(self.attempt.score_percent, Decimal('33.33'))
        participant = self.attempt.participant
        participant.refresh_from_db()
        self.assertEqual(participant.attempts_used, 1)
        self.assertEqual(participant.best_score_percent, Decimal('33.33'))
        row = build_report_row(report_participants(participant.cycle).get(pk=participant.pk))
        self.assertEqual(row.status, 'Failed')
        self.assertTrue(row.completed)
        self.assertEqual(close_expired_periodic_attempts(now=NOW + timedelta(days=4)), 0)

    def test_closes_even_when_learner_access_is_now_disabled(self):
        PeriodicExamSettings.objects.filter(organization=self.organization).update(enabled=False)
        self.assertEqual(close_expired_periodic_attempts(now=NOW + timedelta(days=3)), 1)

    def test_summary_closes_the_learners_own_expired_attempt(self):
        summary = periodic_exam_summary(self.learner, now=NOW + timedelta(minutes=5))
        self.assertIsNone(summary['open_attempt_id'])
        self.assertEqual(summary['last_completed_attempt_id'], self.attempt.id)
        self.assertEqual(summary['attempts_used'], 1)
        self.assertTrue(summary['can_start'])

    def test_report_endpoint_and_command_close_expired_attempts(self):
        admin = User.objects.create_user(
            email='abandon-admin@example.com', password='Pass1234', role=User.Role.ORG_ADMIN,
            organization=self.organization,
        )
        client = APIClient()
        client.force_authenticate(admin)
        cycle = self.attempt.participant.cycle
        with patch('django.utils.timezone.now', return_value=NOW + timedelta(hours=1)):
            response = client.get(f'/api/periodic-exams/report/cycles/{cycle.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['status'], 'Failed')

        retake = start(self.learner, now=NOW + timedelta(minutes=1), seed=5)
        out = StringIO()
        with patch('django.utils.timezone.now', return_value=NOW + timedelta(hours=1)):
            call_command('close_expired_periodic_exam_attempts', stdout=out)
        self.assertIn('Closed 1 expired', out.getvalue())
        retake.refresh_from_db()
        self.assertIsNotNone(retake.submitted_at)
