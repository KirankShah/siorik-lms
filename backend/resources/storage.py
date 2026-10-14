from django.conf import settings
from django.core.files.storage import FileSystemStorage


def resource_storage():
    """Use the durable resource directory configured for this application."""
    return FileSystemStorage(location=settings.RESOURCE_MEDIA_ROOT)
