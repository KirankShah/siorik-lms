from django.core.management.base import BaseCommand

from org_settings.services import send_due_inactivity_reminders

REMINDER_TYPE_LABEL = {
    'logged_in_inactive': 'logged-in-but-inactive',
    'never_logged_in': 'never-logged-in',
}


class Command(BaseCommand):
    """
    Sends the two configurable inactivity reminder emails — "logged in but
    never engaged" and "never logged in at all" — for every organization
    that has them enabled (org_settings.OrganizationSettings) and is due per
    its own configured frequency. See org_settings.services for the full
    eligibility/due-check/email logic; this command is just the entry point.

    Intended to run once daily via a cPanel Cron Job — this hosting
    environment has no background task worker (no Celery), so a scheduled
    management command is the correct mechanism instead. Example cron entry
    (see backend/scripts/README or the deploy docs for the exact path on
    this project's production server):

        cd /path/to/backend && source venv/bin/activate && python manage.py send_inactivity_reminders

    Safe to run more than once a day — an organization's own last-sent
    timestamp means a reminder that isn't due yet is simply skipped, not
    re-sent.
    """

    help = 'Sends configured inactivity reminder emails (logged-in-inactive, never-logged-in) to due organizations.'

    def handle(self, *args, **options):
        summaries = send_due_inactivity_reminders()

        if not summaries:
            self.stdout.write('No organizations were due for an inactivity reminder.')
            return

        for summary in summaries:
            label = REMINDER_TYPE_LABEL[summary['reminder_type']]
            self.stdout.write(
                f"{summary['organization']}: {label} reminder sent to {summary['recipient_count']} "
                f"staff member(s) at {summary['sent_at'].isoformat()}."
            )
        self.stdout.write(self.style.SUCCESS(f'Done — {len(summaries)} reminder batch(es) sent.'))
