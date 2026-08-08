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


class DemoUserProvisioningError(Exception):
    """Raised for any per-row failure provisioning a single demo user (duplicate email,
    invalid input, or the invite email failing to send). Callers report `str(exc)` back
    to the admin rather than letting it propagate as a 500."""


def generate_temp_password() -> str:
    """
    A random password, not a passphrase — this is emailed once and immediately
    replaced by the user's own choice via the forced-reset flow, so memorability
    doesn't matter. secrets.choice (not `random`) for cryptographic randomness.
    Called once per user (see provision_demo_user), never reused across a batch.
    """
    return ''.join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(TEMP_PASSWORD_LENGTH))


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

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


@transaction.atomic
def provision_demo_user(*, name, email, organization, designation='', phone_number=''):
    """
    Creates a single demo LEARNER account with a system-generated temporary
    password and emails an invite. The whole operation (account creation +
    email) is atomic: if the invite email fails to send, the account is rolled
    back rather than left stranded with a password nobody received — the
    caller can safely retry the same row.

    Raises DemoUserProvisioningError with a human-readable reason on any
    failure (duplicate email, invalid input, email send failure).
    """
    email = (email or '').strip().lower()
    if not email or '@' not in email:
        raise DemoUserProvisioningError('Invalid email address.')
    if User.objects.filter(email__iexact=email).exists():
        raise DemoUserProvisioningError('A user with this email already exists.')

    name = (name or '').strip()
    if not name:
        raise DemoUserProvisioningError('Name is required.')
    first_name, _, last_name = name.partition(' ')

    if organization is None:
        raise DemoUserProvisioningError('Organization is required.')

    temp_password = generate_temp_password()
    user = User.objects.create_user(
        email=email,
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.LEARNER,
        organization=organization,
        designation=(designation or '').strip(),
        phone_number=(phone_number or '').strip(),
        is_demo=True,
        must_reset_password=True,
    )

    try:
        send_demo_user_invite_email(user, temp_password)
    except Exception as exc:
        raise DemoUserProvisioningError(f'Account created but the invite email failed to send: {exc}') from exc

    return user
