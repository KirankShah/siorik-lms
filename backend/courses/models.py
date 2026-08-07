from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import Organization
from accounts.validators import validate_image_size

from .validators import LESSON_TYPE_ALLOWED_EXTENSIONS, validate_lesson_file_size

MAX_DESCRIPTION_LENGTH = 10_000


class SlideTemplate(models.Model):
    """A curated visual theme for CONTENT slides — background/text/accent colors
    chosen as a fixed, designed set rather than a raw color picker, so a
    course's slides stay visually consistent instead of becoming a
    mismatched patchwork. Seeded via migration; not user-creatable via the API.
    """

    name = models.CharField(max_length=100, unique=True)
    # A CSS `background` value — a solid color or a simple linear-gradient().
    background_css = models.CharField(max_length=255)
    # Paired with background_css for legibility — dark text for light
    # backgrounds, light text for dark ones.
    text_color = models.CharField(max_length=20)
    # Used for headings, quote accents, and links within the slide content.
    accent_color = models.CharField(max_length=20)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Course(models.Model):
    class ContentOwner(models.TextChoices):
        PLATFORM = 'PLATFORM', 'Platform'
        ORGANIZATION = 'ORGANIZATION', 'Organization'

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
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
    # Null means the pre-templates default look (white background, dark
    # text) — this is the course's actual visual identity for every CONTENT
    # slide that doesn't set its own Slide.template_override, not just a
    # default for new slides. See Slide.template_override.
    template = models.ForeignKey(
        SlideTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
    )
    # Course-wide average score (across each quiz's best attempt) required
    # before a certificate can issue — NOT a requirement that every
    # individual quiz independently score above this threshold; a quiz's own
    # Quiz.pass_percentage is a separate per-quiz pass/fail indicator that
    # doesn't itself gate the certificate. See
    # certificates.services.certificate_ineligibility_reason.
    certificate_pass_threshold = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    certificate_expiry_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Months after issuance the certificate expires. Null means it never expires.',
    )
    # Null means fall back to whichever CertificateTemplate has is_default=True.
    # See certificates.services.generate_certificate.
    certificate_template = models.ForeignKey(
        'certificates.CertificateTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
    )
    completion_deadline_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Days after enrollment the course should be completed by. Null means no deadline.',
    )
    # Gates whether DemoLessonAccess is even consulted for this course — a demo
    # user is only lesson-restricted when this is True. False (the default)
    # means demo users see this course exactly like any other learner.
    is_demo_available = models.BooleanField(default=False)
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


class DemoLessonAccess(models.Model):
    """
    Marks one Lesson within an is_demo_available Course as visible to demo
    users (accounts.User.is_demo=True). Every other lesson in that course
    renders locked for them — see courses.permissions.is_lesson_locked_for_demo_user
    and the enforcement built on top of it in courses/assessments/assignments/
    scenarios views. Non-demo users are entirely unaffected by this model.
    """

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='demo_lesson_access')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='demo_access_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['lesson__order']
        unique_together = ('course', 'lesson')

    def clean(self):
        super().clean()
        if self.lesson_id and self.course_id and self.lesson.module.course_id != self.course_id:
            raise ValidationError({'lesson': 'This lesson does not belong to the specified course.'})

    def __str__(self):
        return f'{self.course.title} -> {self.lesson.title}'


class Slide(models.Model):
    class SlideType(models.TextChoices):
        CONTENT = 'CONTENT', 'Content'
        QUIZ = 'QUIZ', 'Quiz'
        ASSIGNMENT = 'ASSIGNMENT', 'Assignment'
        SCENARIO = 'SCENARIO', 'Scenario'

    class Layout(models.TextChoices):
        STACKED = 'STACKED', 'Stacked'
        IMAGE_LEFT = 'IMAGE_LEFT', 'Image left'
        IMAGE_RIGHT = 'IMAGE_RIGHT', 'Image right'

    class ImageColumnWidth(models.TextChoices):
        COMPACT = 'COMPACT', 'Compact'
        STANDARD = 'STANDARD', 'Standard'
        WIDE = 'WIDE', 'Wide'

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='slides')
    # Optional — falls back to an auto-numbered "Slide N" (see display_title)
    # rather than storing a computed default that could go stale if order changes.
    title = models.CharField(max_length=255, blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    slide_type = models.CharField(max_length=20, choices=SlideType.choices, default=SlideType.CONTENT)
    # CONTENT slides only — how the frontend renderer arranges this slide's
    # elements. Defaults to STACKED so existing slides render unchanged.
    layout = models.CharField(max_length=20, choices=Layout.choices, default=Layout.STACKED)
    # IMAGE_LEFT/IMAGE_RIGHT only — caps how wide the docked image column is
    # allowed to grow (it still auto-sizes to the image's own aspect ratio up
    # to that cap; see SlideElementsView's canvasMode on the frontend).
    # Standard suits most images; Wide is for text-dense reference images
    # (tables, detailed diagrams) that need more room to stay legible.
    image_column_width = models.CharField(
        max_length=20, choices=ImageColumnWidth.choices, default=ImageColumnWidth.STANDARD
    )
    # Null (the common case) means this slide follows whatever the course's
    # current template is — set this only for the rare slide that should
    # deliberately differ from the rest of the course.
    template_override = models.ForeignKey(
        SlideTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='slide_overrides',
    )
    estimated_minutes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        unique_together = ('lesson', 'order')

    def display_title(self):
        return self.title or f'Slide {self.order}'

    def snapshot_elements(self):
        """JSON-serializable snapshot of this slide's current elements, for SlideRevision."""
        return [
            {
                'id': element.id,
                'order': element.order,
                'element_type': element.element_type,
                'rich_text': element.rich_text,
                'file': element.file.name if element.file else None,
                'video_url': element.video_url,
                'video_file': element.video_file.name if element.video_file else None,
                'embed_url': element.embed_url,
                'caption': element.caption,
                'align': element.align,
            }
            for element in self.elements.order_by('order')
        ]

    def write_revision(self, edited_by=None):
        SlideRevision.objects.create(slide=self, elements_json=self.snapshot_elements(), edited_by=edited_by)

    def __str__(self):
        return f'{self.lesson.title} - {self.display_title()}'


class Element(models.Model):
    class ElementType(models.TextChoices):
        TEXT = 'TEXT', 'Text'
        IMAGE = 'IMAGE', 'Image'
        VIDEO_AUDIO = 'VIDEO_AUDIO', 'Video/Audio'
        BREAKOUT_IMAGE = 'BREAKOUT_IMAGE', 'Breakout image'
        QUOTE = 'QUOTE', 'Quote'
        FILE_DOWNLOAD = 'FILE_DOWNLOAD', 'File download'
        EMBED = 'EMBED', 'Embed'
        PRESENTATION_PDF = 'PRESENTATION_PDF', 'Presentation/PDF'

    class Align(models.TextChoices):
        LEFT = 'LEFT', 'Left'
        CENTER = 'CENTER', 'Center'
        RIGHT = 'RIGHT', 'Right'

    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='elements')
    order = models.PositiveIntegerField(default=0)
    element_type = models.CharField(max_length=20, choices=ElementType.choices, default=ElementType.TEXT)

    # TEXT, QUOTE
    rich_text = models.TextField(blank=True, default='')
    # IMAGE, FILE_DOWNLOAD, PRESENTATION_PDF
    file = models.FileField(upload_to='element_files/', blank=True, null=True, validators=[validate_lesson_file_size])
    # VIDEO_AUDIO — either an upload or a pasted URL
    video_url = models.URLField(blank=True, default='')
    video_file = models.FileField(upload_to='element_videos/', blank=True, null=True, validators=[validate_lesson_file_size])
    # EMBED, BREAKOUT_IMAGE
    embed_url = models.URLField(blank=True, default='')
    # IMAGE, BREAKOUT_IMAGE
    caption = models.CharField(max_length=500, blank=True, default='')
    # IMAGE (horizontal placement within the slide)
    align = models.CharField(max_length=10, choices=Align.choices, default=Align.CENTER)

    class Meta:
        ordering = ['order']
        unique_together = ('slide', 'order')

    def save(self, *args, edited_by=None, **kwargs):
        super().save(*args, **kwargs)
        self.slide.write_revision(edited_by=edited_by)

    def delete(self, *args, edited_by=None, **kwargs):
        slide = self.slide
        super().delete(*args, **kwargs)
        slide.write_revision(edited_by=edited_by)

    def __str__(self):
        return f'{self.slide} - {self.element_type} #{self.order}'


class SlideRevision(models.Model):
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='revisions')
    elements_json = models.JSONField(default=list, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='slide_revisions',
    )
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-edited_at']

    def __str__(self):
        return f'{self.slide} @ {self.edited_at:%Y-%m-%d %H:%M}'


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


class SlideProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='slide_progress')
    slide = models.ForeignKey(Slide, on_delete=models.CASCADE, related_name='progress_entries')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Tracks actual time on slide (not just a completion checkbox) so it can serve
    # as minimum-time-on-slide evidence for compliance-style content.
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['slide__order']
        unique_together = ('enrollment', 'slide')

    def __str__(self):
        return f'{self.enrollment} - {self.slide}'
