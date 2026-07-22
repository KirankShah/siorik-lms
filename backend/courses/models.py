from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import Organization
from accounts.validators import validate_image_size

from .validators import LESSON_TYPE_ALLOWED_EXTENSIONS, validate_lesson_file_size

MAX_DESCRIPTION_LENGTH = 10_000


class Course(models.Model):
    class ContentOwner(models.TextChoices):
        PLATFORM = 'PLATFORM', 'Platform'
        ORGANIZATION = 'ORGANIZATION', 'Organization'

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(MAX_DESCRIPTION_LENGTH)])
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        help_text=(
            'The owning organization for ORGANIZATION-owned courses. Ignored for '
            'access control on PLATFORM-owned courses — see CourseAccess instead.'
        ),
    )
    content_owner = models.CharField(max_length=20, choices=ContentOwner.choices, default=ContentOwner.PLATFORM)
    cover_image = models.ImageField(
        upload_to='course_covers/', blank=True, null=True, validators=[validate_image_size]
    )
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


class CourseAccess(models.Model):
    """
    Grants an organization visibility into a PLATFORM-owned course. Stands in for a
    per-user billing/entitlement step that isn't automated yet — for now, granting
    access is a manual action taken by a PLATFORM_ADMIN.
    """

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='access_grants')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='course_access_grants')
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-granted_at']
        unique_together = ('course', 'organization')

    def __str__(self):
        return f'{self.course.title} -> {self.organization.name}'


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


class Page(models.Model):
    class PageType(models.TextChoices):
        CONTENT = 'CONTENT', 'Content'
        QUIZ = 'QUIZ', 'Quiz'
        ASSIGNMENT = 'ASSIGNMENT', 'Assignment'

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    page_type = models.CharField(max_length=20, choices=PageType.choices, default=PageType.CONTENT)
    content_json = models.JSONField(default=list, blank=True, help_text='BlockNote document for this page.')
    estimated_minutes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        unique_together = ('lesson', 'order')

    def save(self, *args, edited_by=None, **kwargs):
        is_new = self._state.adding
        content_changed = True
        if not is_new:
            previous_content = Page.objects.filter(pk=self.pk).values_list('content_json', flat=True).first()
            content_changed = previous_content != self.content_json

        super().save(*args, **kwargs)

        if is_new or content_changed:
            PageRevision.objects.create(page=self, content_json=self.content_json, edited_by=edited_by)

    def __str__(self):
        return f'{self.lesson.title} - {self.title}'


class PageRevision(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='revisions')
    content_json = models.JSONField(default=list, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='page_revisions',
    )
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-edited_at']

    def __str__(self):
        return f'{self.page} @ {self.edited_at:%Y-%m-%d %H:%M}'


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


class PageProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='page_progress')
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='progress_entries')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Tracks actual time on page (not just a completion checkbox) so it can serve
    # as minimum-time-on-page evidence for compliance-style content.
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['page__order']
        unique_together = ('enrollment', 'page')

    def __str__(self):
        return f'{self.enrollment} - {self.page}'
