import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone

from accounts.models import User
from accounts.services import _send_invite_email, generate_temp_password
from courses.models import Enrollment
from levelassessments.models import LevelAssessmentAttempt

from .models import OrganizationSettings

logger = logging.getLogger(__name__)

_BRAND_NAVY = '#032147'
_BRAND_GOLD = '#e1b862'

# How long "enough time has passed" means for each configured frequency —
# monthly uses a real calendar month (relativedelta), not a fixed 30 days, so
# it doesn't drift against invocation-time-of-month over the year.
REMINDER_FREQUENCY_INTERVALS = {
    OrganizationSettings.ReminderFrequency.DAILY: timedelta(days=1),
    OrganizationSettings.ReminderFrequency.WEEKLY: timedelta(days=7),
    OrganizationSettings.ReminderFrequency.FORTNIGHTLY: timedelta(days=14),
    OrganizationSettings.ReminderFrequency.MONTHLY: relativedelta(months=1),
}


def is_reminder_due(last_sent_at, frequency):
    """True if `last_sent_at` (an organization's logged_in_inactive_last_sent_at
    or never_logged_in_last_sent_at) is None (never sent) or old enough for
    `frequency` to have elapsed."""
    if last_sent_at is None:
        return True
    return timezone.now() >= last_sent_at + REMINDER_FREQUENCY_INTERVALS[frequency]


def _staff_queryset(organization):
    """Real, currently-active LEARNER accounts for `organization` — the same
    population accounts.views.StaffEnrollmentViewSet manages. Deactivated
    staff (is_active=False) are excluded: reminding someone to log in when
    their access has been revoked would be actively wrong, and org
    admins/instructors don't have "assigned training" to be reminded about."""
    return User.objects.filter(organization=organization, role=User.Role.LEARNER, is_demo=False, is_active=True)


def logged_in_inactive_staff(organization):
    """Staff who have logged in at least once but have zero completed
    courses and zero level-assessment attempts — i.e. they have access but
    have never actually engaged with their assigned training."""
    return (
        _staff_queryset(organization)
        .filter(last_login__isnull=False)
        .exclude(enrollments__status=Enrollment.Status.COMPLETED)
        .exclude(level_assessment_attempts__isnull=False)
        .distinct()
    )


def never_logged_in_staff(organization):
    """Staff who have never logged in at all."""
    return _staff_queryset(organization).filter(last_login__isnull=True)


def send_logged_in_inactive_reminder_email(user):
    display_name = user.get_full_name() or user.email
    login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login"
    subject = f'{display_name}, Your Siorik LMS Training Is Waiting'

    text_body = (
        f'Dear {display_name},\n\n'
        f"You have access to Siorik LMS, but haven't started your assigned compliance and "
        f"financial-crime-prevention training yet.\n\n"
        f'Log In to Siorik LMS: {login_url}\n\n'
        f"Once you're in, your assigned training will be waiting on your dashboard — it only takes a "
        f"few minutes to get started.\n\n"
        f'If you have any questions, please contact your training administrator.\n\n'
        f'Best regards,\n'
        f'Siorik Consultancy Pvt. Ltd.'
    )
    html_body = f'''
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto;">
  <p>Dear {display_name},</p>
  <p>You have access to Siorik LMS, but haven't started your assigned compliance and
     financial-crime-prevention training yet.</p>
  <p>
    <a href="{login_url}"
       style="display: inline-block; padding: 12px 28px; background-color: {_BRAND_NAVY}; color: {_BRAND_GOLD};
              text-decoration: none; font-weight: bold; border-radius: 6px;">
      Log In to Siorik LMS &rarr;
    </a>
  </p>
  <p>Once you're in, your assigned training will be waiting on your dashboard — it only takes a few
     minutes to get started.</p>
  <p>If you have any questions, please contact your training administrator.</p>
  <p>
    Best regards,<br>
    Siorik Consultancy Pvt. Ltd.
  </p>
</div>
'''
    _send_invite_email(to_email=user.email, subject=subject, text_body=text_body, html_body=html_body)


def send_never_logged_in_reminder_email(user):
    """
    Reminds a staff member who has never logged in at all. There is no
    self-service "forgot password" flow in this system, so — unlike a simple
    nudge — this may need to actually restore their ability to log in:

    - must_reset_password is (normally always) True for anyone who's never
      logged in, since it can only be cleared via SetPasswordView, which
      itself requires being logged in first. Their original system-generated
      temporary password was never claimed and isn't retrievable (only its
      hash is stored) — so rather than assume the original invite email/
      password are still usable, a fresh one is generated and set here, and
      the email is framed like the original invite (temp password included,
      forced-reset-on-first-login messaging).
    - The must_reset_password=False branch is a safety net for an account
      created outside the normal provisioning flow (e.g. Django admin/
      createsuperuser) that already has a real, self-chosen password but
      somehow never logged in — their password is left untouched, and the
      email is framed as a plain access reminder instead.
    """
    display_name = user.get_full_name() or user.email
    org_name = user.organization.name if user.organization else 'your institution'
    login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login"

    if user.must_reset_password:
        temp_password = generate_temp_password()
        user.set_password(temp_password)
        user.save(update_fields=['password'])

        subject = f'{display_name}, Reminder: Your Siorik LMS Account Is Ready'
        text_body = (
            f'Dear {display_name},\n\n'
            f'An account was created for you on Siorik LMS by {org_name} for your compliance and '
            f"financial-crime-prevention training, but it looks like you haven't logged in yet. "
            f"For your security, here's a fresh temporary password:\n\n"
            f'Email: {user.email}\n'
            f'Temporary Password: {temp_password}\n\n'
            f'Log In to Siorik LMS: {login_url}\n\n'
            f"You'll be asked to set a new password the first time you log in. Once you're in, your "
            f"assigned training will be waiting on your dashboard.\n\n"
            f'If you have any questions, please contact your training administrator.\n\n'
            f'Best regards,\n'
            f'Siorik Consultancy Pvt. Ltd.'
        )
        html_body = f'''
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto;">
  <p>Dear {display_name},</p>
  <p>An account was created for you on Siorik LMS by <strong>{org_name}</strong> for your compliance and
     financial-crime-prevention training, but it looks like you haven't logged in yet. For your security,
     here's a fresh temporary password:</p>
  <p style="margin-bottom: 4px;"><strong>Your login details:</strong></p>
  <p style="margin-top: 0;">
    Email: {user.email}<br>
    Temporary Password: {temp_password}
  </p>
  <p>
    <a href="{login_url}"
       style="display: inline-block; padding: 12px 28px; background-color: {_BRAND_NAVY}; color: {_BRAND_GOLD};
              text-decoration: none; font-weight: bold; border-radius: 6px;">
      Log In to Siorik LMS &rarr;
    </a>
  </p>
  <p>You'll be asked to set a new password the first time you log in. Once you're in, your assigned
     training will be waiting on your dashboard.</p>
  <p>If you have any questions, please contact your training administrator.</p>
  <p>
    Best regards,<br>
    Siorik Consultancy Pvt. Ltd.
  </p>
</div>
'''
    else:
        subject = f'{display_name}, Reminder: You Have Not Yet Logged In to Siorik LMS'
        text_body = (
            f'Dear {display_name},\n\n'
            f'You have an account on Siorik LMS with {org_name}, but our records show you have not yet '
            f'logged in.\n\n'
            f'Log In to Siorik LMS: {login_url}\n\n'
            f"If you're not sure of your password, please contact your training administrator to have it reset.\n\n"
            f'Best regards,\n'
            f'Siorik Consultancy Pvt. Ltd.'
        )
        html_body = f'''
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto;">
  <p>Dear {display_name},</p>
  <p>You have an account on Siorik LMS with <strong>{org_name}</strong>, but our records show you have not
     yet logged in.</p>
  <p>
    <a href="{login_url}"
       style="display: inline-block; padding: 12px 28px; background-color: {_BRAND_NAVY}; color: {_BRAND_GOLD};
              text-decoration: none; font-weight: bold; border-radius: 6px;">
      Log In to Siorik LMS &rarr;
    </a>
  </p>
  <p>If you're not sure of your password, please contact your training administrator to have it reset.</p>
  <p>
    Best regards,<br>
    Siorik Consultancy Pvt. Ltd.
  </p>
</div>
'''

    _send_invite_email(to_email=user.email, subject=subject, text_body=text_body, html_body=html_body)


def send_due_inactivity_reminders():
    """
    The whole job the send_inactivity_reminders management command runs:
    for every organization with either reminder enabled and due (per its own
    configured frequency), email every matching staff member and advance
    that organization's own last-sent timestamp. Returns a list of
    {'organization', 'reminder_type', 'recipient_count', 'sent_at'} summaries
    — one entry per batch actually sent — for the command to log/print.
    """
    now = timezone.now()
    summaries = []

    for org_settings in OrganizationSettings.objects.select_related('organization'):
        organization = org_settings.organization

        if org_settings.logged_in_inactive_reminder_enabled and is_reminder_due(
            org_settings.logged_in_inactive_last_sent_at, org_settings.logged_in_inactive_reminder_frequency
        ):
            recipients = list(logged_in_inactive_staff(organization))
            for user in recipients:
                send_logged_in_inactive_reminder_email(user)
            org_settings.logged_in_inactive_last_sent_at = now
            org_settings.save(update_fields=['logged_in_inactive_last_sent_at'])
            summary = {
                'organization': organization.name, 'reminder_type': 'logged_in_inactive',
                'recipient_count': len(recipients), 'sent_at': now,
            }
            logger.info(
                'Inactivity reminder sent: organization=%s reminder_type=%s recipients=%d at=%s',
                organization.name, 'logged_in_inactive', len(recipients), now.isoformat(),
            )
            summaries.append(summary)

        if org_settings.never_logged_in_reminder_enabled and is_reminder_due(
            org_settings.never_logged_in_last_sent_at, org_settings.never_logged_in_reminder_frequency
        ):
            recipients = list(never_logged_in_staff(organization))
            for user in recipients:
                send_never_logged_in_reminder_email(user)
            org_settings.never_logged_in_last_sent_at = now
            org_settings.save(update_fields=['never_logged_in_last_sent_at'])
            summary = {
                'organization': organization.name, 'reminder_type': 'never_logged_in',
                'recipient_count': len(recipients), 'sent_at': now,
            }
            logger.info(
                'Inactivity reminder sent: organization=%s reminder_type=%s recipients=%d at=%s',
                organization.name, 'never_logged_in', len(recipients), now.isoformat(),
            )
            summaries.append(summary)

    return summaries
