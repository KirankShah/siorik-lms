from django.core.exceptions import ValidationError

MAX_LESSON_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500MB

LESSON_TYPE_ALLOWED_EXTENSIONS = {
    'VIDEO': ['mp4', 'mov', 'webm'],
    'SLIDES': ['pdf', 'pptx'],
    'DOCUMENT': ['pdf', 'docx'],
}


def validate_lesson_file_size(value):
    if value.size > MAX_LESSON_FILE_SIZE_BYTES:
        raise ValidationError(
            f'File size must not exceed {MAX_LESSON_FILE_SIZE_BYTES // (1024 * 1024)}MB.'
        )
