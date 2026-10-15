from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import Organization, User
from levelassessments.models import LevelChoice, LevelQuestion, QuestionSet
from periodic_exams.models import (
    PeriodicExamCycle,
    PeriodicExamCycleQuestion,
    PeriodicExamParticipant,
    PeriodicExamSettings,
)
from periodic_exams.services import PeriodicExamPoolConflictError, ensure_current_cycle


NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)
BEFORE_ALL_TEST_CYCLES = datetime(2025, 1, 1, tzinfo=timezone.utc)
ENABLED_FROM = datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc)


def set_joined(user, joined):
    User.objects.filter(pk=user.pk).update(date_joined=joined)
    user.date_joined = joined


def add_question(organization, level, text, *, question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
                 correct=('A',), option_texts=('First', 'Second'), marks=1):
    assessment_level = organization.assessment_levels.get(name=level)
    question_set, _ = QuestionSet.objects.get_or_create(assessment_level=assessment_level, label='Phase 2 pool')
    question = LevelQuestion.objects.create(
        question_set=question_set,
        question_text=text,
        question_type=question_type,
        marks=marks,
    )
    for order, text_value in enumerate(option_texts):
        LevelChoice.objects.create(
            question=question,
            choice_text=text_value,
            is_correct=chr(ord('A') + order) in correct,
            order=order,
        )
    return question


def enable(organization, *, questions_per_exam=30):
    return PeriodicExamSettings.objects.create(
        organization=organization,
        enabled=True,
        enabled_from=ENABLED_FROM,
        questions_per_exam=questions_per_exam,
    )


class Phase2CycleMaterializationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Phase Two Bank', slug='phase-two-bank')
        enable(self.organization, questions_per_exam=2)
        self.learner = User.objects.create_user(
            email='eligible@example.com',
            password='Pass1234',
            organization=self.organization,
            role=User.Role.LEARNER,
            assessment_level=User.AssessmentLevel.OFFICER,
            first_name='Eligible',
            last_name='Learner',
            branch_department='Operations',
        )
        set_joined(self.learner, BEFORE_ALL_TEST_CYCLES)

    def test_pool_and_participant_snapshots_survive_source_changes(self):
        first = add_question(self.organization, User.AssessmentLevel.OFFICER, '<b>First question?</b>')
        second = add_question(
            self.organization,
            User.AssessmentLevel.OFFICER,
            'Choose both',
            question_type=LevelQuestion.QuestionType.MULTIPLE_ANSWER,
            correct=('A', 'B'),
            option_texts=('One', 'Two', 'Three'),
            marks=2,
        )

        cycle = ensure_current_cycle(self.organization, NOW)
        snapshots = list(cycle.question_pool.order_by('source_question_id_snapshot'))
        participant = cycle.participants.get()
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[1].correct_option_keys, ['A', 'B'])
        self.assertEqual(snapshots[1].choices[0], {'key': 'A', 'text': 'One'})
        self.assertEqual(participant.name_snapshot, 'Eligible Learner')
        self.assertEqual(participant.level_snapshot, User.AssessmentLevel.OFFICER)
        self.assertEqual(participant.branch_department_snapshot, 'Operations')
        self.assertTrue(participant.can_form_full_exam)
        self.assertIsNone(participant.revoked_at)

        first.question_text = 'Edited later'
        first.save(update_fields=['question_text'])
        second.delete()
        self.learner.assessment_level = User.AssessmentLevel.MANAGEMENT
        self.learner.save(update_fields=['assessment_level'])

        snapshots[0].refresh_from_db()
        snapshots[1].refresh_from_db()
        participant.refresh_from_db()
        self.assertEqual(snapshots[0].question_text, '<b>First question?</b>')
        self.assertEqual(snapshots[1].question_text, 'Choose both')
        self.assertIsNone(snapshots[1].source_question_id)
        self.assertEqual(participant.level_snapshot, User.AssessmentLevel.OFFICER)

    def test_normalized_duplicates_collapse_but_conflicts_roll_back(self):
        first = add_question(self.organization, User.AssessmentLevel.OFFICER, '<b>Same question!</b>')
        duplicate = add_question(self.organization, User.AssessmentLevel.OFFICER, ' same QUESTION ')
        cycle = ensure_current_cycle(self.organization, NOW)
        self.assertEqual(cycle.question_pool.count(), 1)
        self.assertEqual(cycle.question_pool.get().source_question_id, first.id)
        self.assertNotEqual(first.id, duplicate.id)

        other = Organization.objects.create(name='Conflict Bank', slug='conflict-bank')
        enable(other, questions_per_exam=1)
        one = add_question(other, User.AssessmentLevel.OFFICER, 'Duplicate?', correct=('A',))
        two = add_question(other, User.AssessmentLevel.OFFICER, 'duplicate', correct=('B',))
        with self.assertRaisesRegex(PeriodicExamPoolConflictError, rf'{one.id} and {two.id}'):
            ensure_current_cycle(other, NOW)
        self.assertFalse(PeriodicExamCycle.objects.filter(organization=other).exists())

    def test_unsupported_question_types_are_excluded(self):
        supported = add_question(self.organization, User.AssessmentLevel.OFFICER, 'Supported')
        unsupported = add_question(self.organization, User.AssessmentLevel.OFFICER, 'Unsupported')
        LevelQuestion.objects.filter(pk=unsupported.pk).update(question_type='ESSAY')

        cycle = ensure_current_cycle(self.organization, NOW)

        self.assertEqual(list(cycle.question_pool.values_list('source_question_id_snapshot', flat=True)), [supported.id])
        self.assertFalse(cycle.participants.get().can_form_full_exam)

    def test_eligibility_is_frozen_at_cycle_start(self):
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Only question')
        cases = [
            ('inactive@example.com', {'is_active': False, 'assessment_level': User.AssessmentLevel.OFFICER}),
            ('instructor@example.com', {'role': User.Role.INSTRUCTOR, 'assessment_level': User.AssessmentLevel.OFFICER}),
            ('demo@example.com', {'is_demo': True, 'assessment_level': User.AssessmentLevel.OFFICER}),
            ('no-level@example.com', {'assessment_level': None}),
            ('joined-on-start@example.com', {'assessment_level': User.AssessmentLevel.OFFICER}),
        ]
        users = []
        for email, fields in cases:
            user = User.objects.create_user(
                email=email, password='Pass1234', organization=self.organization, **fields
            )
            set_joined(user, BEFORE_ALL_TEST_CYCLES)
            users.append(user)
        expected_start = datetime(2026, 10, 17, 18, 15, tzinfo=timezone.utc)
        set_joined(users[-1], expected_start)

        cycle = ensure_current_cycle(self.organization, NOW)

        self.assertEqual(list(cycle.participants.values_list('learner_id_snapshot', flat=True)), [self.learner.id])
        self.assertEqual(cycle.starts_at, expected_start)

        late = User.objects.create_user(
            email='late@example.com', password='Pass1234', organization=self.organization,
            assessment_level=User.AssessmentLevel.OFFICER,
        )
        set_joined(late, cycle.starts_at)
        self.assertEqual(ensure_current_cycle(self.organization, NOW).participants.count(), 1)

    def test_one_thousand_learners_are_materialized_in_bounded_queries(self):
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'One')
        users = [
            User(
                email=f'bulk-{index}@example.com',
                organization=self.organization,
                role=User.Role.LEARNER,
                assessment_level=User.AssessmentLevel.OFFICER,
                is_active=True,
                date_joined=BEFORE_ALL_TEST_CYCLES,
            )
            for index in range(999)
        ]
        User.objects.bulk_create(users, batch_size=500)
        User.objects.filter(email__startswith='bulk-').update(date_joined=BEFORE_ALL_TEST_CYCLES)

        with CaptureQueriesContext(connection) as captured:
            cycle = ensure_current_cycle(self.organization, NOW)

        self.assertEqual(cycle.participants.count(), 1000)
        self.assertLessEqual(len(captured), 25)


class Phase2ConcurrentMaterializationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.organization = Organization.objects.create(name='Concurrent Phase Two', slug='concurrent-phase-two')
        enable(self.organization, questions_per_exam=1)
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Concurrent question')
        learner = User.objects.create_user(
            email='concurrent@example.com', password='Pass1234', organization=self.organization,
            assessment_level=User.AssessmentLevel.OFFICER,
        )
        set_joined(learner, BEFORE_ALL_TEST_CYCLES)

    def _create(self):
        close_old_connections()
        organization = Organization.objects.get(pk=self.organization.pk)
        cycle = ensure_current_cycle(organization, NOW)
        close_old_connections()
        return cycle.pk

    def test_concurrent_calls_create_one_frozen_pool_and_participant_set(self):
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite cannot exercise row-level locking.')
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: self._create(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(PeriodicExamCycle.objects.count(), 1)
        self.assertEqual(PeriodicExamCycleQuestion.objects.count(), 1)
        self.assertEqual(PeriodicExamParticipant.objects.count(), 1)


class Phase2ReadinessApiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Readiness One', slug='readiness-one')
        self.other = Organization.objects.create(name='Readiness Two', slug='readiness-two')
        enable(self.org, questions_per_exam=2)
        enable(self.other, questions_per_exam=1)
        self.admin = User.objects.create_user(
            email='readiness-admin@example.com', password='Pass1234', role=User.Role.ORG_ADMIN,
            organization=self.org,
        )
        self.platform = User.objects.create_user(
            email='readiness-platform@example.com', password='Pass1234', role=User.Role.PLATFORM_ADMIN,
        )
        self.learner = User.objects.create_user(
            email='readiness-learner@example.com', password='Pass1234', organization=self.org,
            assessment_level=User.AssessmentLevel.OFFICER,
        )
        set_joined(self.learner, BEFORE_ALL_TEST_CYCLES)
        self.instructor = User.objects.create_user(
            email='readiness-instructor@example.com', password='Pass1234', role=User.Role.INSTRUCTOR,
            organization=self.org,
        )
        add_question(self.org, User.AssessmentLevel.OFFICER, 'One question')
        add_question(self.other, User.AssessmentLevel.MANAGEMENT, 'Other tenant question')
        self.client = APIClient()

    def test_org_admin_is_tenant_scoped_and_low_count_is_information(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/periodic-exams/readiness/', {'organization_id': self.other.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['organization_id'], self.org.id)
        officer = next(row for row in response.data['levels'] if row['level'] == User.AssessmentLevel.OFFICER)
        self.assertEqual(officer['unique_question_count'], 1)
        self.assertEqual(officer['eligible_learner_count'], 1)
        self.assertFalse(officer['can_form_full_exam'])
        self.assertIn('Cannot form a full exam', officer['note'])

    def test_platform_requires_selector_and_roles_are_denied(self):
        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.get('/api/periodic-exams/readiness/').status_code, 400)
        response = self.client.get('/api/periodic-exams/readiness/', {'organization_id': self.other.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['organization_id'], self.other.id)
        for denied in (self.learner, self.instructor):
            self.client.force_authenticate(denied)
            self.assertEqual(self.client.get('/api/periodic-exams/readiness/').status_code, 403)

    def test_platform_readiness_does_not_create_settings(self):
        organization = Organization.objects.create(name='No Settings', slug='no-settings')
        self.assertFalse(PeriodicExamSettings.objects.filter(organization=organization).exists())
        self.client.force_authenticate(self.platform)

        response = self.client.get('/api/periodic-exams/readiness/', {'organization_id': organization.id})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PeriodicExamSettings.objects.filter(organization=organization).exists())

    def test_conflicting_duplicate_ids_are_returned_to_org_admin(self):
        first = add_question(self.org, User.AssessmentLevel.MANAGEMENT, 'Conflicting text', correct=('A',))
        second = add_question(self.org, User.AssessmentLevel.MANAGEMENT, 'conflicting TEXT!', correct=('B',))
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/periodic-exams/settings/')

        self.assertEqual(response.status_code, 409)
        self.assertIn(str(first.id), response.data['detail'])
        self.assertIn(str(second.id), response.data['detail'])
