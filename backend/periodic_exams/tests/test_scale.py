import random
from datetime import timedelta, timezone as datetime_timezone
from time import perf_counter

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from accounts.models import Organization, User
from levelassessments.models import LevelChoice, LevelQuestion, QuestionSet
from periodic_exams.reminders import send_due_periodic_exam_reminders
from periodic_exams.reports import iter_report_rows, report_participants
from periodic_exams.services import ensure_current_cycle, start_periodic_exam_attempt

from .test_phase2 import BEFORE_ALL_TEST_CYCLES, NOW, enable


class PeriodicExamLumbiniScaleTests(TestCase):
    LEARNER_COUNT = 700
    QUESTION_COUNT = 200
    MAX_SECONDS = 10

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Scale Bank', slug='scale-bank')
        feature = enable(cls.organization, questions_per_exam=30)
        feature.reminders_enabled = True
        feature.reminder_days_before_end = [7, 2]
        feature.save(update_fields=['reminders_enabled', 'reminder_days_before_end'])
        assessment_level = cls.organization.assessment_levels.get(name=User.AssessmentLevel.OFFICER)
        question_set = QuestionSet.objects.create(assessment_level=assessment_level, label='Scale pool')
        questions = LevelQuestion.objects.bulk_create([
            LevelQuestion(
                question_set=question_set,
                question_text=f'Scale question {index}',
                question_type=LevelQuestion.QuestionType.SINGLE_CHOICE,
                marks=1,
                order=index,
            )
            for index in range(cls.QUESTION_COUNT)
        ], batch_size=500)
        LevelChoice.objects.bulk_create([
            LevelChoice(
                question=question,
                choice_text=f'Option {option + 1}',
                is_correct=option == 0,
                order=option,
            )
            for question in questions
            for option in range(2)
        ], batch_size=500)
        User.objects.bulk_create([
            User(
                email=f'scale-{index}@example.com',
                password='!',
                role=User.Role.LEARNER,
                organization=cls.organization,
                assessment_level=User.AssessmentLevel.OFFICER,
                is_active=True,
                is_demo=False,
                date_joined=BEFORE_ALL_TEST_CYCLES,
            )
            for index in range(cls.LEARNER_COUNT)
        ], batch_size=500)
        cls.cycle = ensure_current_cycle(cls.organization, NOW)
        cls.learner = User.objects.get(email='scale-0@example.com')
        cls.due_now = (
            cls.cycle.ends_at - timedelta(days=8)
        ).astimezone(datetime_timezone.utc)

    def test_attempt_start_query_count_and_timing(self):
        started = perf_counter()
        with CaptureQueriesContext(connection) as queries:
            attempt, created = start_periodic_exam_attempt(
                self.learner, now=NOW, rng=random.Random(7)
            )
        elapsed = perf_counter() - started
        self.assertTrue(created)
        self.assertEqual(attempt.paper_questions.count(), 30)
        self.assertLessEqual(len(queries), 25)
        self.assertLess(elapsed, self.MAX_SECONDS)

    def test_report_query_count_and_timing(self):
        started = perf_counter()
        with CaptureQueriesContext(connection) as queries:
            rows = list(iter_report_rows(report_participants(self.cycle)))
        elapsed = perf_counter() - started
        self.assertEqual(len(rows), self.LEARNER_COUNT)
        self.assertLessEqual(len(queries), 3)
        self.assertLess(elapsed, self.MAX_SECONDS)

    def test_reminder_query_count_and_timing(self):
        started = perf_counter()
        with CaptureQueriesContext(connection) as queries:
            result = send_due_periodic_exam_reminders(now=self.due_now, dry_run=True)
        elapsed = perf_counter() - started
        self.assertEqual(result['due'], self.LEARNER_COUNT)
        self.assertLessEqual(len(queries), 15)
        self.assertLess(elapsed, self.MAX_SECONDS)
