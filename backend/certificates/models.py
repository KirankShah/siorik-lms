import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from accounts.models import Organization
from accounts.validators import validate_image_size
from courses.models import Course

PERCENT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]

validate_hex_color = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message='Enter a valid hex color, e.g. #E9B730.',
)


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


class CertificateTemplate(models.Model):
    """
    A branded background image plus calibrated draw positions for the three
    dynamic text fields and the verification QR code. Positions are stored as
    percentages of the background image's own width/height (not raw pixels),
    the same convention assessments.HotspotRegion uses, so a template still
    lines up correctly regardless of the background image's actual resolution.

    `organization` is null for a platform-level template (an organization's
    own template lets it use its own logo/signature background, calibrated
    independently of the platform default), and at most one
    CertificateTemplate may exist per non-null organization (see Meta.constraints)
    — an org calibrates *the* template for itself, not a named list of them.

    generate_certificate() resolves a course's template in three tiers: the
    course's own explicit Course.certificate_template override, else the
    learner's own organization's template (organization=user.organization),
    else whichever platform-level (organization=None) row has is_default=True
    (see save() below, which enforces at most one such default). See
    certificates.services._resolve_template.
    """

    class TextAlign(models.TextChoices):
        LEFT = 'LEFT', 'Left'
        CENTER = 'CENTER', 'Center'
        RIGHT = 'RIGHT', 'Right'

    name = models.CharField(max_length=100)
    # Null means this is a platform-level template (see is_default below) —
    # not tied to any one organization's own branding.
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='certificate_templates',
    )
    background_image = models.ImageField(upload_to='certificate_templates/backgrounds/', validators=[validate_image_size])
    is_default = models.BooleanField(
        default=False,
        help_text=(
            'The platform-wide fallback used by any course/organization without their own certificate template. '
            'Only meaningful (and only settable) on a platform-level template — organization must be empty.'
        ),
    )

    staff_name_x_percent = models.FloatField(default=50.0, validators=PERCENT_VALIDATORS)
    staff_name_y_percent = models.FloatField(default=50.0, validators=PERCENT_VALIDATORS)
    staff_name_font_size = models.PositiveIntegerField(default=60)
    staff_name_color = models.CharField(max_length=7, default='#000000', validators=[validate_hex_color])
    staff_name_font_file = models.FileField(upload_to='certificate_templates/fonts/', blank=True, null=True)
    staff_name_text_align = models.CharField(max_length=6, choices=TextAlign.choices, default=TextAlign.CENTER)

    course_name_x_percent = models.FloatField(default=50.0, validators=PERCENT_VALIDATORS)
    course_name_y_percent = models.FloatField(default=60.0, validators=PERCENT_VALIDATORS)
    course_name_font_size = models.PositiveIntegerField(default=32)
    course_name_color = models.CharField(max_length=7, default='#000000', validators=[validate_hex_color])
    course_name_font_file = models.FileField(upload_to='certificate_templates/fonts/', blank=True, null=True)
    course_name_text_align = models.CharField(max_length=6, choices=TextAlign.choices, default=TextAlign.CENTER)

    issue_date_x_percent = models.FloatField(default=50.0, validators=PERCENT_VALIDATORS)
    issue_date_y_percent = models.FloatField(default=70.0, validators=PERCENT_VALIDATORS)
    issue_date_font_size = models.PositiveIntegerField(default=24)
    issue_date_color = models.CharField(max_length=7, default='#000000', validators=[validate_hex_color])
    issue_date_font_file = models.FileField(upload_to='certificate_templates/fonts/', blank=True, null=True)
    issue_date_text_align = models.CharField(max_length=6, choices=TextAlign.choices, default=TextAlign.CENTER)

    qr_code_x_percent = models.FloatField(default=85.0, validators=PERCENT_VALIDATORS)
    qr_code_y_percent = models.FloatField(default=85.0, validators=PERCENT_VALIDATORS)
    qr_code_size_percent = models.FloatField(default=10.0, validators=PERCENT_VALIDATORS)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'name']
        constraints = [
            # An organization calibrates *the* template for itself — not a
            # named list of several — so at most one row per non-null
            # organization. Platform-level (organization=None) rows are
            # unrestricted in count; is_default picks out which one of those
            # is the fallback (enforced in save() below).
            models.UniqueConstraint(
                fields=['organization'],
                condition=models.Q(organization__isnull=False),
                name='one_certificate_template_per_organization',
            ),
        ]

    def __str__(self):
        label = f'{self.name} — {self.organization.name}' if self.organization_id else self.name
        return f'{label} (default)' if self.is_default else label

    def clean(self):
        if self.is_default and self.organization_id is not None:
            raise ValidationError('Only a platform-level template (no organization) can be the default.')

    def save(self, *args, **kwargs):
        if self.is_default:
            CertificateTemplate.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
