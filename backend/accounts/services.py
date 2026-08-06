import secrets
import string

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import User

TEMP_PASSWORD_LENGTH = 14
_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits + '!@#$%^&*'


class DemoUserProvisioningError(Exception):
    """Raised for any per-row failure provisioning a single demo user (duplicate email,
    invalid input, or the invite email failing to send). Callers report `str(exc)` back
    to the admin rather than letting it propagate as a 500."""


def generate_temp_password() -> str:
    """
    A random password, not a passphrase — this is emailed once and immediately
    replaced by the user's own choice via the forced-reset flow, so memorability
    doesn't matter. secrets.choice (not `random`) for cryptographic randomness.
    """
    return ''.join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(TEMP_PASSWORD_LENGTH))


def send_demo_user_invite_email(user, temp_password):
    login_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/login"
    subject = 'Your demo account is ready'
    message = (
        f'Hi {user.first_name or user.email},\n\n'
        f'An account has been created for you to explore the platform.\n\n'
        f'Login page: {login_url}\n'
        f'Email: {user.email}\n'
        f'Temporary password: {temp_password}\n\n'
        f"You'll be asked to set your own password the first time you log in.\n"
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@transaction.atomic
def provision_demo_user(*, name, email, organization):
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
        is_demo=True,
        must_reset_password=True,
    )

    try:
        send_demo_user_invite_email(user, temp_password)
    except Exception as exc:
        raise DemoUserProvisioningError(f'Account created but the invite email failed to send: {exc}') from exc

    return user
