import uuid

from django.conf import settings
from django.db import models

from courses.models import Course


class Certificate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certificates')
    issued_at = models.DateTimeField(auto_now_add=True)
    certificate_number = models.CharField(max_length=50, unique=True, editable=False)
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text='Null means the certificate never expires.')

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f'{self.certificate_number} - {self.user} - {self.course}'
