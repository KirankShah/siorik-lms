from django.core.management.base import BaseCommand

from periodic_exams.reminders import send_due_periodic_exam_reminders


class Command(BaseCommand):
    help = 'Sends due Periodic Exam reminders using the feature-specific delivery ledger.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List participant IDs that are due without sending email or writing the ledger.',
        )

    def handle(self, *args, **options):
        result = send_due_periodic_exam_reminders(dry_run=options['dry_run'])
        mode = 'Dry run' if options['dry_run'] else 'Run'
        self.stdout.write(
            f"{mode}: due={result['due']} sent={result['sent']} "
            f"failed={result['failed']} duplicate={result['duplicate']}"
        )
        if options['dry_run'] and result['recipients']:
            self.stdout.write(
                'Due participant IDs: ' + ', '.join(str(value) for value in result['recipients'])
            )
