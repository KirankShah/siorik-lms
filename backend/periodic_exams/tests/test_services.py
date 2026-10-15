from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from accounts.models import Organization
from periodic_exams.models import PeriodicExamCycle, PeriodicExamSettings
from periodic_exams.services import ensure_current_cycle, set_feature_enabled, update_operational_settings


class CycleServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Lumbini', slug='lumbini')
        self.settings = PeriodicExamSettings.objects.create(
            organization=self.organization,
            enabled=True,
            enabled_from=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
        )

    def test_cycle_creation_is_idempotent_and_does_not_create_missed_cycles(self):
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        first = ensure_current_cycle(self.organization, now)
        second = ensure_current_cycle(self.organization, now)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PeriodicExamCycle.objects.count(), 1)
        self.assertEqual(first.sequence, 1)

    def test_cycle_freezes_settings_and_later_edits_apply_next_cycle(self):
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        current = ensure_current_cycle(self.organization, now)
        update_operational_settings(self.settings, {'questions_per_exam': 40}, actor=None, now=now)
        current.refresh_from_db()
        self.assertEqual(current.questions_per_exam, 30)
        self.settings.refresh_from_db()
        self.assertEqual(self.settings.questions_per_exam, 40)

    def test_frequency_change_waits_for_first_full_new_period(self):
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        current = ensure_current_cycle(self.organization, now)
        row = update_operational_settings(self.settings, {'frequency': 'QUARTERLY'}, actor=None, now=now)
        self.assertEqual(row.frequency, 'MONTHLY')
        self.assertEqual(row.pending_frequency, 'QUARTERLY')
        self.assertGreaterEqual(row.pending_frequency_effective_at, current.ends_at)

    def test_due_frequency_is_promoted_before_other_settings_are_saved(self):
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        self.settings.pending_frequency = 'QUARTERLY'
        self.settings.pending_frequency_effective_at = datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc)
        self.settings.save()
        row = update_operational_settings(self.settings, {'questions_per_exam': 31}, actor=None, now=now)
        self.assertEqual(row.frequency, 'QUARTERLY')
        self.assertIsNone(row.pending_frequency)
        self.assertEqual(row.questions_per_exam, 31)

    def test_first_enable_waits_for_next_full_cycle(self):
        organization = Organization.objects.create(name='New', slug='new')
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        row = set_feature_enabled(organization, True, actor=None, now=now)
        self.assertGreater(row.enabled_from, now)
        self.assertIsNone(ensure_current_cycle(organization, now))

    def test_disable_then_reenable_in_same_cycle_preserves_cycle(self):
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        cycle = ensure_current_cycle(self.organization, now)
        set_feature_enabled(self.organization, False, actor=None, now=now)
        self.assertIsNone(ensure_current_cycle(self.organization, now))
        row = set_feature_enabled(self.organization, True, actor=None, now=now)
        self.assertEqual(row.enabled_from, cycle.starts_at)
        self.assertEqual(ensure_current_cycle(self.organization, now).pk, cycle.pk)


class ConcurrentCycleCreationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.organization = Organization.objects.create(name='Concurrent', slug='concurrent')
        PeriodicExamSettings.objects.create(
            organization=self.organization,
            enabled=True,
            enabled_from=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
        )

    def _create(self):
        close_old_connections()
        organization = Organization.objects.get(pk=self.organization.pk)
        cycle = ensure_current_cycle(organization, datetime(2026, 10, 20, tzinfo=timezone.utc))
        close_old_connections()
        return cycle.pk

    def test_concurrent_calls_create_one_cycle(self):
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite cannot exercise row-level locking.')
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: self._create(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(PeriodicExamCycle.objects.count(), 1)
