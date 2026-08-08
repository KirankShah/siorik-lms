import secrets
import string

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction

from .models import User

TEMP_PASSWORD_LENGTH = 14
_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits + '!@#$%^&*'

_BRAND_NAVY = '#032147'
_BRAND_GOLD = '#e1b862'


class UserProvisioningError(Exception):
    """Raised for any per-row failure provisioning a demo user or org admin account
    (duplicate email, invalid input, or the invite email failing to send). Callers
    report `str(exc)` back to the admin rather than letting it propagate as a 500."""


def generate_temp_password() -> str:
    """
    A random password, not a passphrase — this is emailed once and immediately
    replaced by the user's own choice via the forced-reset flow, so memorability
    doesn't matter. secrets.choice (not `random`) for cryptographic randomness.
    Called once per user (see provision_demo_user), never reused across a batch.
    """
    return ''.join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(TEMP_PASSWORD_LENGTH))


def _send_invite_email(*, to_email, subject, text_body, html_body):
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


def send_demo_user_invite_email(user, temp_password):
    display_name = user.get_full_name() or user.email
    login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login"
    subject = f'{display_name}, Welcome to Siorik LMS — Demo Access Inside'

    text_body = (
        f'Dear {display_name},\n\n'
        f"Congratulations — you've been granted demo access to Siorik LMS.\n\n"
        f"Siorik LMS is Nepal's first learning management system built specifically for financial crime "
        f'prevention — purpose-designed for banks and financial institutions to train staff on AML/CFT, '
        f'compliance, and risk management, rather than adapted from a generic corporate training platform.\n\n'
        f'Your login details:\n\n'
        f'Email: {user.email}\n'
        f'Temporary Password: {temp_password}\n\n'
        f'Log In to Siorik LMS: {login_url}\n\n'
        f"For your security, you'll be asked to set a new password the first time you log in.\n\n"
        f'If you have any questions or would like to discuss bringing Siorik LMS to your institution, simply '
        f'reply to this email.\n\n'
        f'Best regards,\n'
        f'Siorik Consultancy Pvt. Ltd.'
    )

    html_body = f'''
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto;">
  <p>Dear {display_name},</p>
  <p>Congratulations — you've been granted demo access to Siorik LMS.</p>
  <p>
    Siorik LMS is Nepal's first learning management system built specifically for financial crime
    prevention — purpose-designed for banks and financial institutions to train staff on AML/CFT,
    compliance, and risk management, rather than adapted from a generic corporate training platform.
  </p>
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
  <p>For your security, you'll be asked to set a new password the first time you log in.</p>
  <p>
    If you have any questions or would like to discuss bringing Siorik LMS to your institution, simply
    reply to this email.
  </p>
  <p>
    Best regards,<br>
    Siorik Consultancy Pvt. Ltd.
  </p>
</div>
'''

    _send_invite_email(to_email=user.email, subject=subject, text_body=text_body, html_body=html_body)


def send_org_admin_invite_email(user, temp_password):
    display_name = user.get_full_name() or user.email
    org_name = user.organization.name if user.organization else 'your institution'
    login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login"
    subject = f"{display_name}, You've Been Added as Administrator for {org_name} on Siorik LMS"

    text_body = (
        f'Dear {display_name},\n\n'
        f"You've been granted administrator access to Siorik LMS for {org_name}.\n\n"
        f"As an organization administrator, you can manage your institution's learners, monitor training "
        f'progress, and access compliance reports for your team.\n\n'
        f'Your login details:\n\n'
        f'Email: {user.email}\n'
        f'Temporary Password: {temp_password}\n\n'
        f'Log In to Siorik LMS: {login_url}\n\n'
        f"For your security, you'll be asked to set a new password the first time you log in.\n\n"
        f'If you have any questions, simply reply to this email.\n\n'
        f'Best regards,\n'
        f'Siorik Consultancy Pvt. Ltd.'
    )

    html_body = f'''
<div style="font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; max-width: 560px; margin: 0 auto;">
  <p>Dear {display_name},</p>
  <p>You've been granted administrator access to Siorik LMS for <strong>{org_name}</strong>.</p>
  <p>
    As an organization administrator, you can manage your institution's learners, monitor training
    progress, and access compliance reports for your team.
  </p>
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
  <p>For your security, you'll be asked to set a new password the first time you log in.</p>
  <p>If you have any questions, simply reply to this email.</p>
  <p>
    Best regards,<br>
    Siorik Consultancy Pvt. Ltd.
  </p>
</div>
'''

    _send_invite_email(to_email=user.email, subject=subject, text_body=text_body, html_body=html_body)


def _create_pending_user(*, name, email, organization, role, is_demo, designation='', phone_number=''):
    """
    Shared validation + account creation for both provision_demo_user and
    provision_org_admin — everything except which role/is_demo it's created
    with and which invite email gets sent. Returns (user, temp_password).
    """
    email = (email or '').strip().lower()
    if not email or '@' not in email:
        raise UserProvisioningError('Invalid email address.')
    if User.objects.filter(email__iexact=email).exists():
        raise UserProvisioningError('A user with this email already exists.')

    name = (name or '').strip()
    if not name:
        raise UserProvisioningError('Name is required.')
    first_name, _, last_name = name.partition(' ')

    if organization is None:
        raise UserProvisioningError('Organization is required.')

    temp_password = generate_temp_password()
    user = User.objects.create_user(
        email=email,
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        role=role,
        organization=organization,
        designation=(designation or '').strip(),
        phone_number=(phone_number or '').strip(),
        is_demo=is_demo,
        must_reset_password=True,
    )
    return user, temp_password


@transaction.atomic
def provision_demo_user(*, name, email, organization, designation='', phone_number=''):
    """
    Creates a single demo LEARNER account with a system-generated temporary
    password and emails an invite. The whole operation (account creation +
    email) is atomic: if the invite email fails to send, the account is rolled
    back rather than left stranded with a password nobody received — the
    caller can safely retry the same row.

    Raises UserProvisioningError with a human-readable reason on any
    failure (duplicate email, invalid input, email send failure).
    """
    user, temp_password = _create_pending_user(
        name=name, email=email, organization=organization, role=User.Role.LEARNER, is_demo=True,
        designation=designation, phone_number=phone_number,
    )

    try:
        send_demo_user_invite_email(user, temp_password)
    except Exception as exc:
        raise UserProvisioningError(f'Account created but the invite email failed to send: {exc}') from exc

    return user


@transaction.atomic
def provision_org_admin(*, name, email, organization, designation='', phone_number=''):
    """
    Creates an ORG_ADMIN account for `organization` with a system-generated
    temporary password and emails an invite — same mechanics as
    provision_demo_user (atomic, forced password reset on first login), but
    is_demo=False (a real org admin isn't a prospective-client demo account,
    so shouldn't get the demo-catalog visibility that flag grants) and a
    distinctly-worded invite email (not "demo access" — this is a real,
    ongoing administrator role for their own institution).
    """
    user, temp_password = _create_pending_user(
        name=name, email=email, organization=organization, role=User.Role.ORG_ADMIN, is_demo=False,
        designation=designation, phone_number=phone_number,
    )

    try:
        send_org_admin_invite_email(user, temp_password)
    except Exception as exc:
        raise UserProvisioningError(f'Account created but the invite email failed to send: {exc}') from exc

    return user
