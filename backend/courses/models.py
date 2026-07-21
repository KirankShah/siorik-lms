from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import Organization

from .validators import LESSON_TYPE_ALLOWED_EXTENSIONS, validate_lesson_file_size


class Course(models.Model):
    class ContentOwner(models.TextChoices):
        PLATFORM = 'PLATFORM', 'Platform'
        ORGANIZATION = 'ORGANIZATION', 'Organization'

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        help_text='Null means platform/managed content.',
    )
    content_owner = models.CharField(max_length=20, choices=ContentOwner.choices, default=ContentOwner.PLATFORM)
    cover_image = models.ImageField(upload_to='course_covers/', blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_courses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('course', 'order')

    def __str__(self):
        return f'{self.course.title} - {self.title}'


class Lesson(models.Model):
    class LessonType(models.TextChoices):
        VIDEO = 'VIDEO', 'Video'
        SLIDES = 'SLIDES', 'Slides'
        DOCUMENT = 'DOCUMENT', 'Document'
        TEXT = 'TEXT', 'Text'

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    lesson_type = models.CharField(max_length=20, choices=LessonType.choices, default=LessonType.TEXT)
    content_file = models.FileField(
        upload_to='lesson_content/',
        blank=True,
        null=True,
        validators=[validate_lesson_file_size],
    )
    content_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    estimated_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('module', 'order')

    def clean(self):
        super().clean()
        if self.content_file:
            extension = self.content_file.name.rsplit('.', 1)[-1].lower()
            allowed_extensions = LESSON_TYPE_ALLOWED_EXTENSIONS.get(self.lesson_type)
            if allowed_extensions and extension not in allowed_extensions:
                raise ValidationError({
                    'content_file': (
                        f"'.{extension}' files are not allowed for lesson type {self.lesson_type}. "
                        f"Allowed extensions: {', '.join(allowed_extensions)}."
                    )
                })

    def __str__(self):
        return f'{self.module.title} - {self.title}'


class Enrollment(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Not started'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        COMPLETED = 'COMPLETED', 'Completed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    progress_percent = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = ('user', 'course')

    def __str__(self):
        return f'{self.user} - {self.course}'


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress_entries')
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['lesson__order']
        unique_together = ('enrollment', 'lesson')

    def __str__(self):
        return f'{self.enrollment} - {self.lesson}'
