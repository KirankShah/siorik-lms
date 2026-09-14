from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

MAX_RESOURCE_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


def validate_resource_file_size(value):
    if value.size > MAX_RESOURCE_FILE_SIZE_BYTES:
        raise ValidationError(f'File size must not exceed {MAX_RESOURCE_FILE_SIZE_BYTES // (1024 * 1024)}MB.')


def validate_pdf_content(value):
    """
    FileExtensionValidator (below) only checks the filename; this additionally
    cross-checks the browser-supplied content_type and sniffs the actual
    bytes for the '%PDF-' magic number, so a renamed .pptx/.docx (right
    extension, wrong content) can't slip through.
    """
    content_type = getattr(value, 'content_type', None)
    if content_type and content_type != 'application/pdf':
        raise ValidationError('Only PDF files are allowed.')

    value.seek(0)
    header = value.read(5)
    value.seek(0)
    if header != b'%PDF-':
        raise ValidationError('This file does not appear to be a valid PDF.')


RESOURCE_FILE_VALIDATORS = [
    validate_resource_file_size,
    FileExtensionValidator(allowed_extensions=['pdf']),
    validate_pdf_content,
]
