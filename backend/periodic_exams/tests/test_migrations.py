from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class InitialMigrationTests(TransactionTestCase):
    serialized_rollback = True
    migrate_from = [('periodic_exams', None)]
    migrate_to = [('periodic_exams', '0001_initial')]

    def test_apply_and_reverse_preserve_existing_organization(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state([('accounts', '0010_staffinvitationjob_staffinvitation')]).apps
        Organization = old_apps.get_model('accounts', 'Organization')
        organization = Organization.objects.create(name='Existing', slug='existing')

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        Settings = apps.get_model('periodic_exams', 'PeriodicExamSettings')
        Settings.objects.create(organization_id=organization.pk)
        self.assertTrue(Organization.objects.filter(pk=organization.pk).exists())

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state([('accounts', '0010_staffinvitationjob_staffinvitation')]).apps
        self.assertTrue(old_apps.get_model('accounts', 'Organization').objects.filter(pk=organization.pk).exists())

        MigrationExecutor(connection).migrate(self.migrate_to)
