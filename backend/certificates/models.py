import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

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

    generate_certificate() resolves a course's template via
    Course.certificate_template, falling back to whichever row here has
    is_default=True (see save() below, which enforces at most one default).
    """

    class TextAlign(models.TextChoices):
        LEFT = 'LEFT', 'Left'
        CENTER = 'CENTER', 'Center'
        RIGHT = 'RIGHT', 'Right'

    name = models.CharField(max_length=100)
    background_image = models.ImageField(upload_to='certificate_templates/backgrounds/', validators=[validate_image_size])
    is_default = models.BooleanField(
        default=False,
        help_text='The platform-wide fallback used by any course without its own certificate_template set.',
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

    def __str__(self):
        return f'{self.name} (default)' if self.is_default else self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            CertificateTemplate.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
