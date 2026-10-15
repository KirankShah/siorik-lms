from django.core.management.base import BaseCommand

from periodic_exams.services import close_expired_periodic_attempts


class Command(BaseCommand):
    help = 'Finalizes abandoned Periodic Exam attempts whose question timers have all run out.'

    def handle(self, *args, **options):
        closed = close_expired_periodic_attempts()
        self.stdout.write(f'Closed {closed} expired Periodic Exam attempt(s).')
