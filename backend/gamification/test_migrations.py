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
