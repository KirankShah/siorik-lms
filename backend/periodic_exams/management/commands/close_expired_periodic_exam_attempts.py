from django.core.management.base import BaseCommand

from periodic_exams.services import close_expired_periodic_attempts, revoke_ineligible_participants


class Command(BaseCommand):
    help = (
        'Finalizes abandoned Periodic Exam attempts whose question timers have all run out, '
        'and revokes open-cycle participants who are no longer eligible.'
    )

    def handle(self, *args, **options):
        closed = close_expired_periodic_attempts()
        revoked = revoke_ineligible_participants()
        self.stdout.write(f'Closed {closed} expired Periodic Exam attempt(s); revoked {revoked} participant(s).')
