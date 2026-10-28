from django.core.management.base import BaseCommand

from periodic_exams.reminders import send_due_periodic_exam_reminders


class Command(BaseCommand):
    help = (
        'Sends a rate-limited batch of Periodic Exam notifications. Run hourly; '
        'the delivery ledger resumes remaining recipients without duplicates.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List participant IDs that are due without sending email or writing the ledger.',
        )
        parser.add_argument(
            '--batch-size', type=int, default=None,
            help='Maximum SMTP delivery attempts for this run (default: 50).',
        )

    def handle(self, *args, **options):
        result = send_due_periodic_exam_reminders(
            dry_run=options['dry_run'], max_deliveries=options['batch_size'],
        )
        mode = 'Dry run' if options['dry_run'] else 'Run'
        self.stdout.write(
            f"{mode}: due={result['due']} activation_due={result['activation_due']} "
            f"deadline_due={result['deadline_due']} sent={result['sent']} "
            f"failed={result['failed']} duplicate={result['duplicate']} "
            f"remaining={result['remaining']}"
        )
        if options['dry_run'] and result['recipients']:
            self.stdout.write(
                'Due participant IDs: ' + ', '.join(str(value) for value in result['recipients'])
            )
