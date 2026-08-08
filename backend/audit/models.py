from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = 'LOGIN', 'Login'
        COURSE_CREATED = 'COURSE_CREATED', 'Course created'
        CERTIFICATE_GENERATED = 'CERTIFICATE_GENERATED', 'Certificate generated'
        ENROLLMENT_CREATED = 'ENROLLMENT_CREATED', 'Enrollment created'
        ENROLLMENT_UPDATED = 'ENROLLMENT_UPDATED', 'Enrollment updated'
        DEMO_USER_CREATED = 'DEMO_USER_CREATED', 'Demo user created'
        PASSWORD_RESET_COMPLETED = 'PASSWORD_RESET_COMPLETED', 'Password reset completed'
        ORGANIZATION_CREATED = 'ORGANIZATION_CREATED', 'Organization created'
        ORG_ADMIN_CREATED = 'ORG_ADMIN_CREATED', 'Organization admin created'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.action} {self.object_type}:{self.object_id} by {self.user}'
