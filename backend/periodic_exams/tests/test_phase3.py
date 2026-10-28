import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from unittest.mock import patch
from rest_framework.test import APIClient

from accounts.models import Organization, User
from certificates.models import Certificate
from gamification.models import LeaderboardEntry, UserBadge
from levelassessments.models import LevelQuestion
from periodic_exams.models import (
    PeriodicExamAttempt,
    PeriodicExamAttemptQuestion,
    PeriodicExamParticipant,
    PeriodicExamQuestionUsage,
)
from periodic_exams.services import (
    PeriodicExamError,
    advance_periodic_attempt,
    catch_up_periodic_attempt,
    get_periodic_attempt,
    grade_selection,
    periodic_attempt_payload,
    periodic_exam_summary,
    save_periodic_answer,
    select_questions_for_participant,
    set_feature_enabled,
    start_periodic_exam_attempt,
    submit_periodic_attempt,
)

from .test_phase2 import BEFORE_ALL_TEST_CYCLES, ENABLED_FROM, NOW, add_question, enable, set_joined


def configure(settings, *, questions=3, attempts=3, seconds=5, pass_mark=60):
    settings.questions_per_exam = questions
    settings.max_attempts_per_cycle = attempts
    settings.seconds_per_question = seconds
    settings.pass_mark_percent = pass_mark
    settings.save(update_fields=[
        'questions_per_exam', 'max_attempts_per_cycle', 'seconds_per_question', 'pass_mark_percent'
    ])


def make_learner(organization, email, *, level=User.AssessmentLevel.OFFICER):
    learner = User.objects.create_user(
        email=email,
        password='Pass1234',
        role=User.Role.LEARNER,
        organization=organization,
        assessment_level=level,
    )
    set_joined(learner, BEFORE_ALL_TEST_CYCLES)
    return learner


class PeriodicExamPhase3ServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Phase Three Bank', slug='phase-three-bank')
        self.settings = enable(self.organization, questions_per_exam=3)
        configure(self.settings)
        for index in range(8):
            add_question(self.organization, User.AssessmentLevel.OFFICER, f'Question {index + 1}')
        self.first = make_learner(self.organization, 'first@example.com')
        self.second = make_learner(self.organization, 'second@example.com')
        self.cycle = self.organization.periodic_exam_cycles.none().first()

    def start(self, learner=None, *, now=NOW, seed=1):
        return start_periodic_exam_attempt(learner or self.first, now=now, rng=random.Random(seed))[0]

    def correct_current(self, attempt, *, now):
        row = attempt.paper_questions.select_related('cycle_question').get(order=attempt.current_question_index)
        save_periodic_answer(
            attempt.participant.learner,
            attempt.id,
            current_question_index=attempt.current_question_index,
            selected_option_keys=row.cycle_question.correct_option_keys,
            now=now,
        )

    def complete(self, attempt, *, correct=True, start_time=NOW):
        now = start_time
        for index in range(attempt.paper_questions.count()):
            attempt.refresh_from_db()
            row = attempt.paper_questions.select_related('cycle_question').get(order=index)
            selected = row.cycle_question.correct_option_keys if correct else []
            save_periodic_answer(
                attempt.participant.learner,
                attempt.id,
                current_question_index=index,
                selected_option_keys=selected,
                now=now,
            )
            if index == attempt.paper_questions.count() - 1:
                attempt = submit_periodic_attempt(attempt.participant.learner, attempt.id, now=now)
            else:
                attempt = advance_periodic_attempt(
                    attempt.participant.learner, attempt.id, current_question_index=index, now=now
                )
            now += timedelta(seconds=1)
        return attempt

    def test_different_learners_and_retake_use_fresh_questions_before_fallback(self):
        first_attempt = self.start(self.first, seed=1)
        second_attempt = self.start(self.second, seed=2)
        first_ids = set(first_attempt.paper_questions.values_list('cycle_question_id', flat=True))
        second_ids = set(second_attempt.paper_questions.values_list('cycle_question_id', flat=True))
        self.assertNotEqual(first_ids, second_ids)
        self.complete(first_attempt, correct=False)

        retake = self.start(self.first, now=NOW + timedelta(minutes=1), seed=3)
        retake_ids = set(retake.paper_questions.values_list('cycle_question_id', flat=True))
        self.assertTrue(first_ids.isdisjoint(retake_ids))
        self.assertEqual(retake.paper_questions.count(), 3)
        self.assertEqual(len(retake_ids), 3)
        self.complete(retake, correct=False, start_time=NOW + timedelta(minutes=1))
        # Only 2 of the 8 questions remain unused this cycle; a third paper would
        # have to repeat one, so the retake is refused instead.
        with self.assertRaises(PeriodicExamError) as error:
            self.start(self.first, now=NOW + timedelta(minutes=2), seed=31)
        self.assertEqual(error.exception.code, 'CYCLE_POOL_EXHAUSTED')
        self.assertEqual(retake.participant.attempts.count(), 2)

    def test_level_pool_isolation(self):
        for index in range(3):
            add_question(
                self.organization, User.AssessmentLevel.MANAGEMENT, f'Management question {index}'
            )
        manager = make_learner(
            self.organization, 'manager@example.com', level=User.AssessmentLevel.MANAGEMENT
        )
        attempt = self.start(manager, seed=32)
        self.assertEqual(
            set(attempt.paper_questions.values_list('cycle_question__level', flat=True)),
            {User.AssessmentLevel.MANAGEMENT},
        )

    def test_lifetime_unused_then_oldest_used_order_is_deterministic(self):
        attempt = self.start(seed=4)
        participant = attempt.participant
        self.complete(attempt, correct=False)
        questions = list(participant.cycle.question_pool.filter(level=participant.level_snapshot).order_by('id'))
        PeriodicExamQuestionUsage.objects.filter(learner=self.first).delete()
        base = NOW - timedelta(days=20)
        for index, question in enumerate(questions[:6]):
            PeriodicExamQuestionUsage.objects.create(
                learner=self.first,
                level=participant.level_snapshot,
                question_key=question.normalized_text_hash,
                first_cycle_sequence=1,
                last_cycle_sequence=1 if index == 0 else 2,
                last_used_at=base + timedelta(days=index),
            )
        participant.attempts.all().delete()

        selected, _usages = select_questions_for_participant(
            participant, now=NOW, rng=random.Random(9)
        )
        selected_keys = {question.normalized_text_hash for question in selected}
        lifetime_unused_keys = {question.normalized_text_hash for question in questions[6:]}
        self.assertTrue(lifetime_unused_keys.issubset(selected_keys))
        self.assertIn(questions[0].normalized_text_hash, selected_keys)

    def test_pool_too_small_attempt_cap_pass_clear_and_best_score(self):
        attempt = self.start(seed=5)
        failed = self.complete(attempt, correct=False)
        self.assertEqual(failed.score_percent, Decimal('0.00'))
        self.assertEqual(periodic_exam_summary(self.first, now=NOW + timedelta(minutes=1))['status'], 'RETAKE')
        historical_now = failed.participant.cycle.ends_at + timedelta(days=1)
        retake = start_periodic_exam_attempt(
            self.first, cycle_id=failed.participant.cycle_id, now=historical_now, rng=random.Random(6),
        )[0]
        passed = self.complete(retake, correct=True, start_time=historical_now)
        passed.participant.refresh_from_db()
        self.assertEqual(passed.participant.attempts_used, 2)
        self.assertEqual(passed.participant.best_score_percent, Decimal('100.00'))
        self.assertIsNotNone(passed.participant.passed_at)
        with self.assertRaisesRegex(PeriodicExamError, 'already been passed'):
            self.start(now=NOW + timedelta(minutes=2), seed=7)

        small_org = Organization.objects.create(name='Small Pool', slug='small-pool')
        small_settings = enable(small_org, questions_per_exam=2)
        configure(small_settings, questions=2)
        add_question(small_org, User.AssessmentLevel.OFFICER, 'Only one')
        learner = make_learner(small_org, 'small@example.com')
        with self.assertRaisesRegex(PeriodicExamError, 'Cannot form a full exam') as error:
            start_periodic_exam_attempt(learner, now=NOW)
        self.assertEqual(error.exception.code, 'INSUFFICIENT_POOL')

    def test_attempt_limit_counts_started_attempts(self):
        configure(self.settings, attempts=1)
        attempt = self.start(seed=8)
        self.complete(attempt, correct=False)
        summary = periodic_exam_summary(self.first, now=NOW + timedelta(minutes=1))
        self.assertEqual(summary['status'], 'FAILED')
        self.assertTrue(summary['completed'])
        self.assertEqual(summary['attempts_remaining'], 0)
        with self.assertRaises(PeriodicExamError) as error:
            self.start(now=NOW + timedelta(minutes=1), seed=9)
        self.assertEqual(error.exception.code, 'ATTEMPT_LIMIT_REACHED')

    def test_exact_set_grading_for_single_and_multiple_answer(self):
        self.assertTrue(grade_selection(['A'], ['A']))
        self.assertFalse(grade_selection(['A', 'B'], ['A']))
        self.assertTrue(grade_selection(['B', 'A'], ['A', 'B']))
        self.assertFalse(grade_selection(['A'], ['A', 'B']))

    def test_timer_save_resume_multi_question_catch_up_and_auto_submit(self):
        attempt = self.start(seed=10)
        first_row = attempt.paper_questions.select_related('cycle_question').get(order=0)
        save_periodic_answer(
            self.first,
            attempt.id,
            current_question_index=0,
            selected_option_keys=first_row.cycle_question.correct_option_keys,
            now=NOW + timedelta(seconds=1),
        )
        caught = get_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(seconds=11))
        self.assertEqual(caught.current_question_index, 2)
        rows = list(caught.paper_questions.order_by('order'))
        self.assertTrue(rows[0].is_correct)
        self.assertFalse(rows[1].is_correct)
        self.assertIsNone(rows[2].locked_at)

        submitted = get_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(seconds=16))
        self.assertIsNotNone(submitted.submitted_at)
        self.assertEqual(submitted.submission_reason, PeriodicExamAttempt.SubmissionReason.QUESTION_TIMEOUT)
        self.assertEqual(submitted.score_percent, Decimal('33.33'))

    def test_no_backtracking_client_time_irrelevant_and_double_submit_idempotent(self):
        attempt = self.start(seed=11)
        advance_periodic_attempt(self.first, attempt.id, current_question_index=0, now=NOW + timedelta(seconds=1))
        with self.assertRaises(PeriodicExamError) as error:
            save_periodic_answer(
                self.first, attempt.id, current_question_index=0,
                selected_option_keys=['A'], now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(error.exception.code, 'STALE_QUESTION')
        advance_periodic_attempt(self.first, attempt.id, current_question_index=1, now=NOW + timedelta(seconds=2))
        first_result = submit_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(seconds=3))
        second_result = submit_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(days=10))
        self.assertEqual(first_result.submitted_at, second_result.submitted_at)
        self.assertEqual(first_result.score_percent, second_result.score_percent)

    def test_started_before_cycle_end_can_finish_after_end(self):
        cycle = self.start(seed=12).participant.cycle
        PeriodicExamAttempt.objects.all().delete()
        PeriodicExamQuestionUsage.objects.all().delete()
        started = self.start(now=cycle.ends_at - timedelta(seconds=2), seed=13)
        resumed = get_periodic_attempt(self.first, started.id, now=cycle.ends_at + timedelta(seconds=1))
        self.assertIsNone(resumed.submitted_at)
        self.assertEqual(resumed.current_question_index, 0)

    def test_start_is_refused_when_the_resolved_cycle_has_ended(self):
        attempt = self.start(seed=121)
        cycle = attempt.participant.cycle
        PeriodicExamAttempt.objects.all().delete()
        PeriodicExamQuestionUsage.objects.all().delete()
        with patch('periodic_exams.services.ensure_current_cycle', return_value=cycle):
            with self.assertRaises(PeriodicExamError) as error:
                self.start(now=cycle.ends_at + timedelta(seconds=1), seed=122)
        self.assertEqual(error.exception.code, 'CYCLE_CLOSED')

    def test_disable_reenable_revoked_and_subscription_lock(self):
        attempt = self.start(seed=14)
        set_feature_enabled(self.organization, False, actor=None, now=NOW + timedelta(seconds=1))
        with self.assertRaises(PeriodicExamError) as disabled:
            get_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(seconds=2))
        self.assertEqual(disabled.exception.code, 'FEATURE_DISABLED')
        set_feature_enabled(self.organization, True, actor=None, now=NOW + timedelta(seconds=3))
        self.assertEqual(get_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(seconds=4)).id, attempt.id)

        participant = attempt.participant
        participant.revoked_at = NOW
        participant.save(update_fields=['revoked_at'])
        with self.assertRaises(PeriodicExamError) as revoked:
            get_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(seconds=4))
        self.assertEqual(revoked.exception.code, 'REVOKED')
        participant.revoked_at = None
        participant.save(update_fields=['revoked_at'])

        org_settings = self.organization.settings
        org_settings.subscription_start_date = NOW.date() - timedelta(days=2)
        org_settings.subscription_duration_days = 1
        org_settings.save(update_fields=['subscription_start_date', 'subscription_duration_days'])
        with self.assertRaises(PeriodicExamError) as expired:
            get_periodic_attempt(self.first, attempt.id, now=NOW + timedelta(seconds=4))
        self.assertEqual(expired.exception.code, 'SUBSCRIPTION_EXPIRED')

    def test_submission_updates_current_knowledge_without_other_side_effects(self):
        before = {
            'certificates': Certificate.objects.count(),
            'badges': UserBadge.objects.count(),
            'leaderboard': LeaderboardEntry.objects.count(),
            'level': self.first.assessment_level,
        }
        attempt = self.start(seed=15)
        self.complete(attempt, correct=True)
        self.first.refresh_from_db()
        self.assertEqual(Certificate.objects.count(), before['certificates'])
        self.assertEqual(UserBadge.objects.count(), before['badges'])
        self.assertEqual(LeaderboardEntry.objects.count(), before['leaderboard'] + 1)
        entry = LeaderboardEntry.objects.get(user=self.first)
        self.assertEqual(entry.latest_periodic_exam_score, Decimal('100'))
        self.assertIsNone(entry.knowledge_score)
        self.assertEqual(entry.total_points, 0)
        self.assertEqual(self.first.assessment_level, before['level'])

    def test_start_query_count_is_bounded_for_large_pool(self):
        for index in range(300):
            add_question(self.organization, User.AssessmentLevel.OFFICER, f'Large pool {index}')
        participant = PeriodicExamParticipant.objects.none()
        with CaptureQueriesContext(connection) as captured:
            attempt = self.start(seed=16)
        self.assertEqual(attempt.paper_questions.count(), 3)
        self.assertLessEqual(len(captured), 30)


class PeriodicExamPhase3ApiTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='API Bank', slug='api-bank')
        settings = enable(self.organization, questions_per_exam=2)
        configure(settings, questions=2, attempts=2, pass_mark=50)
        add_question(self.organization, User.AssessmentLevel.OFFICER, 'Single')
        add_question(
            self.organization,
            User.AssessmentLevel.OFFICER,
            'Multiple',
            question_type=LevelQuestion.QuestionType.MULTIPLE_ANSWER,
            correct=('A', 'B'),
            option_texts=('One', 'Two', 'Three'),
        )
        self.learner = make_learner(self.organization, 'api-learner@example.com')
        self.other = make_learner(self.organization, 'api-other@example.com')
        other_org = Organization.objects.create(name='Other API Bank', slug='other-api-bank')
        other_settings = enable(other_org, questions_per_exam=1)
        configure(other_settings, questions=1)
        add_question(other_org, User.AssessmentLevel.OFFICER, 'Other')
        self.other_org_learner = make_learner(other_org, 'api-other-org@example.com')
        self.client = APIClient()
        self.client.force_authenticate(self.learner)

    def test_endpoints_never_return_answer_keys_or_review(self):
        forbidden = ('correct_option_keys', 'is_correct', 'marks_awarded', 'locked_at')

        summary = self.client.get('/api/periodic-exams/me/summary/')
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertIsNone(summary.data['last_completed_attempt_id'])
        for key in forbidden:
            self.assertNotIn(key, str(summary.data))

        response = self.client.post('/api/periodic-exams/me/attempts/start/')
        self.assertEqual(response.status_code, 201, response.data)
        attempt_id = response.data['id']
        for key in forbidden:
            self.assertNotIn(key, str(response.data))

        retrieved = self.client.get(f'/api/periodic-exams/me/attempts/{attempt_id}/')
        self.assertEqual(retrieved.status_code, 200, retrieved.data)
        for key in forbidden:
            self.assertNotIn(key, str(retrieved.data))

        index = response.data['current_question_index']
        selected = [response.data['current_question']['choices'][0]['key']]
        saved = self.client.put(
            f'/api/periodic-exams/me/attempts/{attempt_id}/current-answer/',
            {'current_question_index': index, 'selected_option_keys': selected},
            format='json',
        )
        self.assertEqual(saved.status_code, 200)
        for key in forbidden:
            self.assertNotIn(key, str(saved.data))

        advanced = self.client.post(
            f'/api/periodic-exams/me/attempts/{attempt_id}/advance/',
            {'current_question_index': 0}, format='json',
        )
        self.assertEqual(advanced.status_code, 200, advanced.data)
        for key in forbidden:
            self.assertNotIn(key, str(advanced.data))

        submitted = self.client.post(f'/api/periodic-exams/me/attempts/{attempt_id}/submit/')
        self.assertEqual(submitted.status_code, 200)
        for key in forbidden:
            self.assertNotIn(key, str(submitted.data))
        result = self.client.get(f'/api/periodic-exams/me/attempts/{attempt_id}/result/')
        self.assertEqual(set(result.data), {'score_percent', 'passed'})
        for key in forbidden:
            self.assertNotIn(key, str(result.data))
        completed_summary = self.client.get('/api/periodic-exams/me/summary/')
        self.assertEqual(completed_summary.data['last_completed_attempt_id'], attempt_id)

    def test_other_learner_and_other_organization_attempt_ids_return_404(self):
        attempt = start_periodic_exam_attempt(self.other, now=NOW, rng=random.Random(1))[0]
        advance_periodic_attempt(
            self.other, attempt.id, current_question_index=0, now=NOW + timedelta(seconds=1)
        )
        advance_periodic_attempt(
            self.other, attempt.id, current_question_index=1, now=NOW + timedelta(seconds=2)
        )
        own_summary = self.client.get('/api/periodic-exams/me/summary/')
        self.assertEqual(own_summary.status_code, 200)
        self.assertIsNone(own_summary.data['last_completed_attempt_id'])
        response = self.client.get(f'/api/periodic-exams/me/attempts/{attempt.id}/')
        self.assertEqual(response.status_code, 404)
        other_attempt = start_periodic_exam_attempt(
            self.other_org_learner, now=NOW, rng=random.Random(1)
        )[0]
        response = self.client.get(f'/api/periodic-exams/me/attempts/{other_attempt.id}/')
        self.assertEqual(response.status_code, 404)

    def test_summary_and_role_denials(self):
        summary = self.client.get('/api/periodic-exams/me/summary/')
        self.assertEqual(summary.status_code, 200)
        self.assertTrue(summary.data['can_start'])
        self.assertEqual(summary.data['status'], 'PENDING')
        history = self.client.get('/api/periodic-exams/me/history/')
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.data), 1)
        self.assertEqual(history.data[0]['cycle']['id'], summary.data['cycle']['id'])
        for role in (User.Role.INSTRUCTOR, User.Role.ORG_ADMIN, User.Role.PLATFORM_ADMIN):
            user = User.objects.create_user(
                email=f'{role.lower()}@example.com', password='Pass1234', role=role,
                organization=None if role == User.Role.PLATFORM_ADMIN else self.organization,
            )
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/periodic-exams/me/summary/').status_code, 403)


class PeriodicExamPhase3ConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.organization = Organization.objects.create(name='Concurrency Bank', slug='concurrency-bank')
        settings = enable(self.organization, questions_per_exam=2)
        configure(settings, questions=2, attempts=2)
        for index in range(4):
            add_question(self.organization, User.AssessmentLevel.OFFICER, f'Concurrent {index}')
        self.learner = make_learner(self.organization, 'concurrent-phase3@example.com')

    def _start(self):
        close_old_connections()
        learner = User.objects.get(pk=self.learner.pk)
        result = start_periodic_exam_attempt(learner, now=NOW, rng=random.Random(1))[0].pk
        close_old_connections()
        return result

    def test_concurrent_double_start_creates_one_attempt(self):
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite cannot exercise row-level locking.')
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: self._start(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(PeriodicExamAttempt.objects.count(), 1)
        self.assertEqual(PeriodicExamAttemptQuestion.objects.count(), 2)

    def _advance(self, attempt_id):
        close_old_connections()
        learner = User.objects.get(pk=self.learner.pk)
        result = advance_periodic_attempt(
            learner, attempt_id, current_question_index=0, now=NOW + timedelta(seconds=6)
        ).current_question_index
        close_old_connections()
        return result

    def test_concurrent_advance_and_timeout_exactly_one_transition_wins(self):
        attempt = start_periodic_exam_attempt(self.learner, now=NOW, rng=random.Random(2))[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            indexes = list(pool.map(lambda _: self._advance(attempt.id), range(2)))
        attempt.refresh_from_db()
        self.assertEqual(indexes, [1, 1])
        self.assertEqual(attempt.current_question_index, 1)
        self.assertEqual(attempt.paper_questions.filter(locked_at__isnull=False).count(), 1)
