"""Regression tests for review problems 4-8: revocation, formula guard, lock-free
cycle reads, the local normalizer, and claim-before-send reminders."""
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from accounts.models import Organization, User
from levelassessments.services import normalize_question_text as level_assessment_normalize
from periodic_exams.models import PeriodicExamCycle, PeriodicExamReminderDelivery
from periodic_exams.reminders import send_due_periodic_exam_reminders
from periodic_exams.reports import spreadsheet_safe
from periodic_exams.services import (
    PeriodicExamError,
    ensure_current_cycle,
    revoke_ineligible_participants,
    start_periodic_exam_attempt,
)
from periodic_exams.text import normalize_question_text

from .test_phase2 import NOW, add_question, enable
from .test_phase3 import make_learner
from .test_phase6 import local_instant


class RevocationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Revoke Bank', slug='revoke-bank')
        self.other = Organization.objects.create(name='Other Revoke Bank', slug='other-revoke-bank')
        enable(self.organization, questions_per_exam=1)
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Revoke question')
        self.learner = make_learner(self.organization, 'revoke@example.com')
        self.cycle = ensure_current_cycle(self.organization, NOW)
        self.participant = self.cycle.participants.get(learner=self.learner)

    def assert_revoked(self, expected=True):
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.revoked_at is not None, expected)

    def test_deactivation_revokes_through_the_save_signal(self):
        self.learner.is_active = False
        self.learner.save(update_fields=['is_active'])
        self.assert_revoked()

    def test_moving_organization_or_role_or_demo_revokes(self):
        for change in (
            {'organization': self.other},
            {'role': User.Role.INSTRUCTOR},
            {'is_demo': True},
        ):
            with self.subTest(change=change):
                type(self.participant).objects.filter(pk=self.participant.pk).update(revoked_at=None)
                User.objects.filter(pk=self.learner.pk).update(
                    organization=self.organization, role=User.Role.LEARNER, is_demo=False,
                )
                learner = User.objects.get(pk=self.learner.pk)
                for field, value in change.items():
                    setattr(learner, field, value)
                learner.save()
                self.assert_revoked()

    def test_level_change_and_unrelated_saves_do_not_revoke(self):
        self.learner.assessment_level = User.AssessmentLevel.MANAGEMENT
        self.learner.save()
        self.learner.save(update_fields=['last_login'])
        self.assert_revoked(False)

    def test_bulk_update_is_caught_by_the_sweep_and_access_is_denied(self):
        User.objects.filter(pk=self.learner.pk).update(organization=self.other)
        self.assert_revoked(False)
        self.assertEqual(revoke_ineligible_participants(cycle=self.cycle, now=NOW), 1)
        self.assert_revoked()
        User.objects.filter(pk=self.learner.pk).update(organization=self.organization)
        with self.assertRaises(PeriodicExamError) as error:
            start_periodic_exam_attempt(User.objects.get(pk=self.learner.pk), now=NOW)
        self.assertEqual(error.exception.code, 'REVOKED')

    def test_deleted_learner_is_revoked_and_ended_cycles_are_untouched(self):
        self.learner.delete()
        self.assertEqual(revoke_ineligible_participants(now=self.cycle.ends_at + timedelta(days=1)), 0)
        self.assertEqual(revoke_ineligible_participants(now=NOW), 1)
        self.assert_revoked()


class FormulaGuardTests(TestCase):
    def test_every_formula_trigger_is_neutralised(self):
        for value in ('=1+1', '+1', '-1', '@SUM(A1)', '\t=1', '\r=1', '\n=1'):
            with self.subTest(value=repr(value)):
                self.assertEqual(spreadsheet_safe(value), "'" + value)
        self.assertEqual(spreadsheet_safe('Plain नेपाली'), 'Plain नेपाली')
        self.assertEqual(spreadsheet_safe(5), 5)


class LockFreeCycleReadTests(TestCase):
    def test_existing_cycle_is_returned_without_row_locks(self):
        organization = Organization.objects.create(name='Lock Bank', slug='lock-bank')
        enable(organization, questions_per_exam=1)
        cycle = ensure_current_cycle(organization, NOW)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(ensure_current_cycle(organization, NOW + timedelta(hours=1)), cycle)
        self.assertFalse(any('FOR UPDATE' in query['sql'].upper() for query in queries.captured_queries))
        self.assertLessEqual(len(queries.captured_queries), 2)
        self.assertEqual(PeriodicExamCycle.objects.filter(organization=organization).count(), 1)


class NormalizerParityTests(TestCase):
    def test_matches_level_assessment_normalization(self):
        for text in (
            '<b>What is KYC?</b>', 'What&nbsp;is   KYC', 'ＫＹＣ — what?', 'केवाईसी के हो?', '', None,
        ):
            with self.subTest(text=text):
                self.assertEqual(normalize_question_text(text), level_assessment_normalize(text))


class ClaimBeforeSendReminderTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Claim Bank', slug='claim-bank')
        settings = enable(self.organization, questions_per_exam=1)
        settings.reminders_enabled = True
        settings.save(update_fields=['reminders_enabled'])
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Claim question')
        self.learner = make_learner(self.organization, 'claim@example.com')
        self.cycle = ensure_current_cycle(self.organization, NOW)
        self.due_now = NOW

    def test_ledger_claim_is_written_before_the_email_is_sent(self):
        seen = []

        def sender(participant, days):
            delivery = PeriodicExamReminderDelivery.objects.get(participant=participant)
            seen.append((delivery.attempt_count, delivery.last_attempt_at, delivery.sent_at))

        result = send_due_periodic_exam_reminders(now=self.due_now, email_sender=sender)
        self.assertEqual(result['sent'], 1)
        self.assertEqual(seen, [(1, self.due_now, None)])
        self.assertIsNotNone(PeriodicExamReminderDelivery.objects.get().sent_at)

    def test_unconfirmed_claim_is_not_resent(self):
        participant = self.cycle.participants.get(learner=self.learner)
        PeriodicExamReminderDelivery.objects.create(
            cycle=self.cycle, participant=participant,
            days_before_end=0,
            attempt_count=1, last_attempt_at=self.due_now - timedelta(minutes=5),
        )
        calls = []
        result = send_due_periodic_exam_reminders(
            now=self.due_now, email_sender=lambda *args: calls.append(args),
        )
        self.assertEqual((result['sent'], result['duplicate']), (0, 1))
        self.assertEqual(calls, [])
