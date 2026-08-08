from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

validate_phone_number = RegexValidator(
    regex=r'^\+?[0-9\s\-()]{7,20}$',
    message='Enter a valid phone number (digits, spaces, +, -, and parentheses only).',
)


def validate_image_size(value):
    if value.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(f'Image size must not exceed {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB.')


class LetterAndDigitPasswordValidator:
    """
    Requires at least one letter and one digit. Django's built-in validators
    don't check this combination — NumericPasswordValidator only rejects
    passwords that are entirely numeric. Paired with MinimumLengthValidator
    (min_length=8), this is exactly the rule the forced-reset dialog displays.
    """

    def validate(self, password, user=None):
        if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            raise ValidationError(
                'Password must contain at least 1 letter and 1 number.',
                code='password_no_letter_or_digit',
            )

    def get_help_text(self):
        return 'Your password must contain at least 1 letter and 1 number.'
