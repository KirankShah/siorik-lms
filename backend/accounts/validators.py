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
