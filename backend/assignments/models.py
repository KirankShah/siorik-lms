from django.conf import settings
from django.db import models

from courses.models import Page


class Assignment(models.Model):
    class SubmissionType(models.TextChoices):
        FILE_UPLOAD = 'FILE_UPLOAD', 'File upload'
        TEXT = 'TEXT', 'Text'

    page = models.OneToOneField(Page, on_delete=models.CASCADE, related_name='assignment')
    instructions_json = models.JSONField(default=list, blank=True, help_text='BlockNote document.')
    submission_type = models.CharField(max_length=20, choices=SubmissionType.choices, default=SubmissionType.FILE_UPLOAD)
    max_marks = models.PositiveIntegerField(default=100)
    due_offset_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Days after enrollment the assignment is due. Null means no due date.',
    )

    def __str__(self):
        return f'Assignment: {self.page.title}'


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignment_submissions')
    submitted_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='assignment_submissions/', blank=True, null=True)
    text_response = models.TextField(blank=True)
    marks_awarded = models.PositiveIntegerField(null=True, blank=True)
    grader_feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.user} - {self.assignment}'
