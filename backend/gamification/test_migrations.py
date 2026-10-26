from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class LeaderboardFreshDatabaseMigrationTests(TransactionTestCase):
    migrate_from = ('gamification', '0010_fix_mysql_latin1_charset')

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        old_targets = [target for target in latest_targets if target[0] != 'gamification'] + [self.migrate_from]
        executor.migrate(old_targets)
        old_apps = executor.loader.project_state(old_targets).apps

        Organization = old_apps.get_model('accounts', 'Organization')
        User = old_apps.get_model('accounts', 'User')
        LeaderboardEntry = old_apps.get_model('gamification', 'LeaderboardEntry')

        organization = Organization.objects.create(name='Migration Test Bank', slug='migration-test-bank')
        user = User.objects.create(
            email='migration-learner@example.com',
            first_name='Migration',
            last_name='Learner',
            role='LEARNER',
            organization=organization,
            password='not-a-real-password',
        )
        self.user_id = user.pk
        self.organization_id = organization.pk
        LeaderboardEntry.objects.create(
            user=user,
            organization=organization,
            total_points=0,
            courses_completed_count=0,
            average_quiz_score=0,
            certificates_earned_count=0,
            level_assessments_passed_count=0,
        )

        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        executor.migrate(latest_targets)
        self.apps = executor.loader.project_state(latest_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_populated_pre_0011_database_reaches_latest_without_data_loss(self):
        Organization = self.apps.get_model('accounts', 'Organization')
        User = self.apps.get_model('accounts', 'User')
        LeaderboardEntry = self.apps.get_model('gamification', 'LeaderboardEntry')

        self.assertTrue(Organization.objects.filter(pk=self.organization_id, name='Migration Test Bank').exists())
        self.assertTrue(User.objects.filter(pk=self.user_id, email='migration-learner@example.com').exists())
        entry = LeaderboardEntry.objects.get(user_id=self.user_id)
        self.assertEqual(entry.organization_id, self.organization_id)
        self.assertEqual(entry.total_points, 0)
        self.assertEqual(entry.courses_completed_count, 0)
        self.assertEqual(entry.average_quiz_score, 0)
        self.assertEqual(entry.certificates_earned_count, 0)
        self.assertEqual(entry.level_assessments_passed_count, 0)
        self.assertIsNone(entry.knowledge_score)


class LeaderboardQuizCoverageMigrationTests(TransactionTestCase):
    migrate_from = ('gamification', '0014_recalculate_current_knowledge')
    migrate_to = ('gamification', '0015_leaderboard_quiz_coverage')

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_additive_fields_apply_and_reverse_without_changing_existing_rows(self):
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        old_targets = [target for target in latest_targets if target[0] != 'gamification'] + [self.migrate_from]
        executor.migrate(old_targets)
        old_apps = executor.loader.project_state(old_targets).apps

        Organization = old_apps.get_model('accounts', 'Organization')
        User = old_apps.get_model('accounts', 'User')
        Entry = old_apps.get_model('gamification', 'LeaderboardEntry')
        organization = Organization.objects.create(name='Coverage Migration Bank', slug='coverage-migration-bank')
        learner = User.objects.create(
            email='coverage-migration@example.com', role='LEARNER', organization=organization,
            password='not-a-real-password',
        )
        entry = Entry.objects.create(
            user=learner, organization=organization, total_points=321,
            courses_completed_count=2, average_quiz_score=75,
            current_course_quiz_average=80, latest_level_assessment_score=70,
            knowledge_score=74,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        migrated_apps = executor.loader.project_state([self.migrate_to]).apps
        migrated = migrated_apps.get_model('gamification', 'LeaderboardEntry').objects.get(pk=entry.pk)
        self.assertEqual(migrated.total_points, 321)
        self.assertEqual(migrated.knowledge_score, 74)
        self.assertEqual((migrated.quizzes_completed, migrated.quizzes_required), (0, 0))

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        reversed_apps = executor.loader.project_state([self.migrate_from]).apps
        reversed_entry = reversed_apps.get_model('gamification', 'LeaderboardEntry').objects.get(pk=entry.pk)
        self.assertEqual(reversed_entry.total_points, 321)
        self.assertEqual(reversed_entry.knowledge_score, 74)


class PeriodicExamScoreMigrationTests(TransactionTestCase):
    migrate_from = ('gamification', '0016_recalculate_question_weighted_scores')
    migrate_to = ('gamification', '0017_use_periodic_exam_score')

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_level_assessment_value_is_not_relabelled_as_a_periodic_exam_score(self):
        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()
        old_targets = [target for target in latest_targets if target[0] != 'gamification'] + [self.migrate_from]
        executor.migrate(old_targets)
        old_apps = executor.loader.project_state(old_targets).apps

        Organization = old_apps.get_model('accounts', 'Organization')
        User = old_apps.get_model('accounts', 'User')
        Entry = old_apps.get_model('gamification', 'LeaderboardEntry')
        organization = Organization.objects.create(name='Periodic Migration Bank', slug='periodic-migration-bank')
        learner = User.objects.create(
            email='periodic-migration@example.com', role='LEARNER', organization=organization,
            password='not-a-real-password',
        )
        Entry.objects.create(
            user=learner, organization=organization,
            current_course_quiz_average=80,
            latest_level_assessment_score=70,
            knowledge_score=74,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        migrated_apps = executor.loader.project_state([self.migrate_to]).apps
        migrated = migrated_apps.get_model('gamification', 'LeaderboardEntry').objects.get(user_id=learner.pk)

        self.assertIsNone(migrated.latest_periodic_exam_score)
        self.assertIsNone(migrated.knowledge_score)
