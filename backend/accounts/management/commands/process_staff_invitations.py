from django.core.management.base import BaseCommand

from accounts.invitation_queue import process_next_staff_invitation_batch


class Command(BaseCommand):
    help = 'Send the next queued staff-invitation batch, subject to the hourly safety interval.'

    def handle(self, *args, **options):
        result = process_next_staff_invitation_batch()
        self.stdout.write(str(result))
