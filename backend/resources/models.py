import uuid

from django.conf import settings
from django.db import models

from accounts.models import Organization

from .validators import RESOURCE_FILE_VALIDATORS


def _resource_upload_path(instance, filename):
    # A random name, not the uploaded title/filename: the PDF is only ever
    # served through the authenticated stream action (see
    # resources.views.ResourceViewSet.stream) rather than this raw storage
    # path being handed to any client, but an unguessable name still raises
    # the bar against someone who finds/guesses a bare /media/resources/...
    # URL directly, same convention as courses.views.MediaUploadView.
    return f'resources/{uuid.uuid4().hex}.pdf'


class Resource(models.Model):
    """
    An org-scoped PDF document an org admin uploads for their own learners to
    view in a protected in-browser viewer (never downloadable through the
    normal UI — see resources.views.ResourceViewSet.stream). Deliberately
    flat: no course/lesson association and no versioning — this is a
    standalone document library per organization, not course content.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    file = models.FileField(upload_to=_resource_upload_path, validators=RESOURCE_FILE_VALIDATORS)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title
