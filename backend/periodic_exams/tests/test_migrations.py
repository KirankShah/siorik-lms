from datetime import date, datetime, timezone

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

PHASE3 = [('periodic_exams', '0003_periodicexamattempt_periodicexamattemptquestion_and_more')]
REMINDER_LEDGER = [('periodic_exams', '0004_periodicexamreminderdelivery')]
LATEST = [('periodic_exams', '0005_fixed_monthly_notifications')]


class Phase2MigrationTests(TransactionTestCase):
    migrate_from = [('periodic_exams', '0001_initial')]
    migrate_to = [('periodic_exams', '0002_periodicexamparticipant_periodicexamcyclequestion_and_more')]

    def test_apply_and_reverse_preserve_populated_existing_tables(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Organization = old_apps.get_model('accounts', 'Organization')
        Settings = old_apps.get_model('periodic_exams', 'PeriodicExamSettings')
        Cycle = old_apps.get_model('periodic_exams', 'PeriodicExamCycle')
        organization = Organization.objects.create(name='Existing', slug='existing')
        Settings.objects.create(organization_id=organization.pk, enabled=True)
        cycle = Cycle.objects.create(
            organization_id=organization.pk,
            sequence=1,
            frequency_snapshot='MONTHLY',
            configuration_version=1,
            questions_per_exam=30,
            pass_mark_percent=60,
            seconds_per_question=60,
            max_attempts_per_cycle=2,
            reminders_enabled=False,
            reminder_days_before_end=[7, 2],
            starts_at=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 17, 18, 15, tzinfo=timezone.utc),
            start_date_ad=date(2026, 7, 17),
            end_date_ad=date(2026, 8, 17),
            start_year_bs=2083,
            start_month_bs=4,
            start_day_bs=1,
            end_year_bs=2083,
            end_month_bs=4,
            end_day_bs=32,
            fiscal_year_start_bs=2083,
            period_number=1,
            display_label='2083 Shrawan',
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        Snapshot = apps.get_model('periodic_exams', 'PeriodicExamCycleQuestion')
        Participant = apps.get_model('periodic_exams', 'PeriodicExamParticipant')
        Snapshot.objects.create(
            cycle_id=cycle.pk,
            level='officer',
            source_question_id_snapshot=123,
            normalized_text='question',
            normalized_text_hash='a' * 64,
            question_text='Question?',
            question_type='SINGLE_CHOICE',
            marks=1,
            choices=[{'key': 'A', 'text': 'Answer'}],
            correct_option_keys=['A'],
        )
        Participant.objects.create(
            cycle_id=cycle.pk,
            learner_id_snapshot=456,
            name_snapshot='Existing Learner',
            email_snapshot='existing@example.com',
            level_snapshot='officer',
            branch_department_snapshot='Branch',
            eligible_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        self.assertTrue(apps.get_model('accounts', 'Organization').objects.filter(pk=organization.pk).exists())
        self.assertTrue(apps.get_model('periodic_exams', 'PeriodicExamSettings').objects.filter(
            organization_id=organization.pk, enabled=True,
        ).exists())
        self.assertTrue(apps.get_model('periodic_exams', 'PeriodicExamCycle').objects.filter(pk=cycle.pk).exists())

        MigrationExecutor(connection).migrate(LATEST)


class Phase3MigrationTests(TransactionTestCase):
    migrate_from = [('periodic_exams', '0002_periodicexamparticipant_periodicexamcyclequestion_and_more')]
    migrate_to = PHASE3

    def test_apply_and_reverse_preserve_populated_phase2_tables(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        Organization = apps.get_model('accounts', 'Organization')
        User = apps.get_model('accounts', 'User')
        Settings = apps.get_model('periodic_exams', 'PeriodicExamSettings')
        Cycle = apps.get_model('periodic_exams', 'PeriodicExamCycle')
        Snapshot = apps.get_model('periodic_exams', 'PeriodicExamCycleQuestion')
        Participant = apps.get_model('periodic_exams', 'PeriodicExamParticipant')
        organization = Organization.objects.create(name='Phase 3 Existing', slug='phase-3-existing')
        user = User.objects.create(
            email='phase3-existing@example.com', password='!', role='LEARNER',
            organization_id=organization.pk, is_active=True,
        )
        Settings.objects.create(organization_id=organization.pk, enabled=True)
        cycle = Cycle.objects.create(
            organization_id=organization.pk, sequence=1, frequency_snapshot='MONTHLY',
            configuration_version=1, questions_per_exam=1, pass_mark_percent=60,
            seconds_per_question=60, max_attempts_per_cycle=2, reminders_enabled=False,
            reminder_days_before_end=[7, 2],
            starts_at=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 17, 18, 15, tzinfo=timezone.utc),
            start_date_ad=date(2026, 7, 17), end_date_ad=date(2026, 8, 17),
            start_year_bs=2083, start_month_bs=4, start_day_bs=1,
            end_year_bs=2083, end_month_bs=4, end_day_bs=32,
            fiscal_year_start_bs=2083, period_number=1, display_label='2083 Shrawan',
        )
        snapshot = Snapshot.objects.create(
            cycle_id=cycle.pk, level='officer', source_question_id_snapshot=999,
            normalized_text='phase three', normalized_text_hash='b' * 64,
            question_text='Phase three?', question_type='SINGLE_CHOICE', marks=1,
            choices=[{'key': 'A', 'text': 'Answer'}], correct_option_keys=['A'],
        )
        participant = Participant.objects.create(
            cycle_id=cycle.pk, learner_id=user.pk, learner_id_snapshot=user.pk,
            name_snapshot='Existing Learner', email_snapshot=user.email,
            level_snapshot='officer', eligible_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        Attempt = apps.get_model('periodic_exams', 'PeriodicExamAttempt')
        AttemptQuestion = apps.get_model('periodic_exams', 'PeriodicExamAttemptQuestion')
        Usage = apps.get_model('periodic_exams', 'PeriodicExamQuestionUsage')
        attempt = Attempt.objects.create(
            participant_id=participant.pk, attempt_number=1,
            started_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
            timer_segment_started_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        )
        AttemptQuestion.objects.create(attempt_id=attempt.pk, cycle_question_id=snapshot.pk, order=0)
        Usage.objects.create(
            learner_id=user.pk, level='officer', question_key='b' * 64,
            first_cycle_sequence=1, last_cycle_sequence=1,
            last_used_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        self.assertTrue(apps.get_model('accounts', 'Organization').objects.filter(pk=organization.pk).exists())
        self.assertTrue(apps.get_model('periodic_exams', 'PeriodicExamCycle').objects.filter(pk=cycle.pk).exists())
        self.assertTrue(apps.get_model('periodic_exams', 'PeriodicExamCycleQuestion').objects.filter(
            pk=snapshot.pk
        ).exists())
        self.assertTrue(apps.get_model('periodic_exams', 'PeriodicExamParticipant').objects.filter(
            pk=participant.pk
        ).exists())

        MigrationExecutor(connection).migrate(LATEST)


class Phase6MigrationTests(TransactionTestCase):
    migrate_from = PHASE3
    migrate_to = REMINDER_LEDGER

    def test_apply_and_reverse_preserve_populated_phase3_tables(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        Organization = apps.get_model('accounts', 'Organization')
        Settings = apps.get_model('periodic_exams', 'PeriodicExamSettings')
        Cycle = apps.get_model('periodic_exams', 'PeriodicExamCycle')
        organization = Organization.objects.create(name='Reminder Existing', slug='reminder-existing')
        Settings.objects.create(organization_id=organization.pk, enabled=True)
        cycle = Cycle.objects.create(
            organization_id=organization.pk, sequence=1, frequency_snapshot='MONTHLY',
            configuration_version=1, questions_per_exam=1, pass_mark_percent=60,
            seconds_per_question=60, max_attempts_per_cycle=2, reminders_enabled=True,
            reminder_days_before_end=[7, 2],
            starts_at=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 17, 18, 15, tzinfo=timezone.utc),
            start_date_ad=date(2026, 7, 17), end_date_ad=date(2026, 8, 17),
            start_year_bs=2083, start_month_bs=4, start_day_bs=1,
            end_year_bs=2083, end_month_bs=4, end_day_bs=32,
            fiscal_year_start_bs=2083, period_number=1, display_label='2083 Shrawan',
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        self.assertEqual(apps.get_model('periodic_exams', 'PeriodicExamReminderDelivery').objects.count(), 0)

        MigrationExecutor(connection).migrate(self.migrate_from)
        apps = MigrationExecutor(connection).loader.project_state(self.migrate_from).apps
        self.assertTrue(apps.get_model('periodic_exams', 'PeriodicExamCycle').objects.filter(pk=cycle.pk).exists())
        self.assertTrue(apps.get_model('periodic_exams', 'PeriodicExamSettings').objects.filter(
            organization_id=organization.pk, enabled=True,
        ).exists())
        MigrationExecutor(connection).migrate(LATEST)


class FixedNotificationMigrationTests(TransactionTestCase):
    migrate_from = REMINDER_LEDGER
    migrate_to = LATEST

    def test_existing_settings_and_cycles_use_only_the_fixed_seven_day_rule(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        Organization = apps.get_model('accounts', 'Organization')
        Settings = apps.get_model('periodic_exams', 'PeriodicExamSettings')
        Cycle = apps.get_model('periodic_exams', 'PeriodicExamCycle')
        organization = Organization.objects.create(name='Fixed Reminder', slug='fixed-reminder')
        Settings.objects.create(
            organization_id=organization.pk, reminders_enabled=False,
            reminder_days_before_end=[7, 2],
        )
        Cycle.objects.create(
            organization_id=organization.pk, sequence=1, frequency_snapshot='MONTHLY',
            configuration_version=1, questions_per_exam=1, pass_mark_percent=60,
            seconds_per_question=60, max_attempts_per_cycle=2, reminders_enabled=False,
            reminder_days_before_end=[7, 2],
            starts_at=datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc),
            ends_at=datetime(2026, 8, 17, 18, 15, tzinfo=timezone.utc),
            start_date_ad=date(2026, 7, 17), end_date_ad=date(2026, 8, 17),
            start_year_bs=2083, start_month_bs=4, start_day_bs=1,
            end_year_bs=2083, end_month_bs=4, end_day_bs=32,
            fiscal_year_start_bs=2083, period_number=1, display_label='2083 Shrawan',
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        settings = apps.get_model('periodic_exams', 'PeriodicExamSettings').objects.get()
        cycle = apps.get_model('periodic_exams', 'PeriodicExamCycle').objects.get()
        self.assertTrue(settings.reminders_enabled)
        self.assertEqual(settings.reminder_days_before_end, [7])
        self.assertTrue(cycle.reminders_enabled)
        self.assertEqual(cycle.reminder_days_before_end, [7])
