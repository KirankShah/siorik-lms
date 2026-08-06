import io
import logging

import qrcode
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from assessments.models import Quiz, QuizAttempt
from audit.models import AuditLog
from audit.services import log_action
from courses.models import Enrollment

from .models import Certificate, CertificateTemplate

logger = logging.getLogger(__name__)

# Margin (as a percent of image width, each side) auto-shrink treats as the
# safe printable area for the staff-name/course-name fields — matches the
# decorative gold border in the default template.
TEXT_SAFE_MARGIN_PERCENT = 8
MIN_AUTO_SHRINK_FONT_SIZE = 16
TEXT_ALIGN_ANCHORS = {
    CertificateTemplate.TextAlign.LEFT: 'lm',
    CertificateTemplate.TextAlign.CENTER: 'mm',
    CertificateTemplate.TextAlign.RIGHT: 'rm',
}


class CertificateIssuanceError(Exception):
    """Raised when a certificate cannot be issued for a user/course combination."""


def generate_certificate(user, course):
    """
    Issue (or return the existing valid) Certificate for a user who has completed a course.

    Requires the user's Enrollment to be COMPLETED, every Quiz linked to the
    course to have at least one passed QuizAttempt by the user, and the
    average of each quiz's best score to meet course.certificate_pass_threshold.
    Raises CertificateIssuanceError if any condition is not met.
    """
    enrollment = Enrollment.objects.filter(user=user, course=course).first()
    if enrollment is None or enrollment.status != Enrollment.Status.COMPLETED:
        raise CertificateIssuanceError('Enrollment must be completed before a certificate can be issued.')

    quizzes = Quiz.objects.filter(slide__lesson__module__course=course)
    best_scores = []
    for quiz in quizzes:
        if not QuizAttempt.objects.filter(user=user, quiz=quiz, passed=True).exists():
            raise CertificateIssuanceError(f'Quiz "{quiz.title}" has not been passed yet.')
        best = QuizAttempt.objects.filter(user=user, quiz=quiz).aggregate(best=Max('score_percent'))['best']
        if best is not None:
            best_scores.append(best)

    if best_scores:
        average_score = sum(best_scores) / len(best_scores)
        if average_score < course.certificate_pass_threshold:
            raise CertificateIssuanceError(
                f'Average score {average_score:.1f}% is below the course pass threshold of '
                f'{course.certificate_pass_threshold}%.'
            )

    existing = Certificate.objects.filter(user=user, course=course).order_by('-issued_at').first()
    if existing and (existing.expires_at is None or existing.expires_at > timezone.now()):
        return existing

    expires_at = None
    if course.certificate_expiry_months:
        expires_at = timezone.now() + relativedelta(months=course.certificate_expiry_months)

    with transaction.atomic():
        certificate = Certificate.objects.create(
            user=user,
            course=course,
            certificate_number=_generate_certificate_number(),
            expires_at=expires_at,
        )
        pdf_bytes = _render_certificate_pdf(certificate)
        certificate.pdf_file.save(f'{certificate.certificate_number}.pdf', ContentFile(pdf_bytes), save=True)

    log_action(user, AuditLog.Action.CERTIFICATE_GENERATED, certificate)
    return certificate


def _generate_certificate_number():
    year = timezone.now().year
    prefix = f'SIORIK-{year}-'

    last = (
        Certificate.objects.select_for_update()
        .filter(certificate_number__startswith=prefix)
        .order_by('-certificate_number')
        .first()
    )
    last_sequence = int(last.certificate_number.rsplit('-', 1)[-1]) if last else 0
    return f'{prefix}{last_sequence + 1:06d}'


def _build_verification_url(token):
    base_url = settings.CERTIFICATE_VERIFICATION_BASE_URL.rstrip('/')
    return f'{base_url}/verify/{token}/'


def _resolve_template(course):
    template = course.certificate_template or CertificateTemplate.objects.filter(is_default=True).first()
    if template is None:
        raise CertificateIssuanceError(
            'No certificate template is configured for this course, and no platform default CertificateTemplate exists.'
        )
    return template


def _read_field_bytes(field_file):
    with field_file.open('rb') as handle:
        return handle.read()


def _load_font(font_file, size):
    if font_file:
        return ImageFont.truetype(io.BytesIO(_read_field_bytes(font_file)), size=size)
    # No .ttf configured for this field yet — falls back to Pillow's bundled
    # scalable default font. This is a placeholder: swap in a matched
    # serif/sans .ttf via the calibration tool once one is sourced.
    logger.warning('CertificateTemplate field has no font_file configured; rendering with Pillow default font.')
    return ImageFont.load_default(size=size)


def _fit_font(font_file, initial_size, text, draw, max_width_px):
    size = initial_size
    font = _load_font(font_file, size)
    while size > MIN_AUTO_SHRINK_FONT_SIZE:
        left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
        if (right - left) <= max_width_px:
            break
        size -= 2
        font = _load_font(font_file, size)
    return font


def _draw_field(draw, image_width, image_height, text, x_percent, y_percent, font, text_align, color):
    x = image_width * x_percent / 100
    y = image_height * y_percent / 100
    draw.text((x, y), text, font=font, fill=color, anchor=TEXT_ALIGN_ANCHORS[text_align])


def _render_certificate_pdf(certificate):
    course = certificate.course
    template = _resolve_template(course)

    image = Image.open(io.BytesIO(_read_field_bytes(template.background_image))).convert('RGB')
    draw = ImageDraw.Draw(image)
    width, height = image.size
    max_text_width_px = width * (1 - 2 * TEXT_SAFE_MARGIN_PERCENT / 100)

    learner_name = certificate.user.get_full_name() or certificate.user.email
    completion_date = certificate.issued_at.strftime('%B %d, %Y')

    staff_name_font = _fit_font(
        template.staff_name_font_file, template.staff_name_font_size, learner_name, draw, max_text_width_px
    )
    _draw_field(
        draw, width, height, learner_name,
        template.staff_name_x_percent, template.staff_name_y_percent,
        staff_name_font, template.staff_name_text_align, template.staff_name_color,
    )

    course_name_font = _fit_font(
        template.course_name_font_file, template.course_name_font_size, course.title, draw, max_text_width_px
    )
    _draw_field(
        draw, width, height, course.title,
        template.course_name_x_percent, template.course_name_y_percent,
        course_name_font, template.course_name_text_align, template.course_name_color,
    )

    issue_date_font = _load_font(template.issue_date_font_file, template.issue_date_font_size)
    _draw_field(
        draw, width, height, completion_date,
        template.issue_date_x_percent, template.issue_date_y_percent,
        issue_date_font, template.issue_date_text_align, template.issue_date_color,
    )

    qr_buffer = io.BytesIO()
    qrcode.make(_build_verification_url(certificate.verification_token)).save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    qr_size_px = max(1, round(width * template.qr_code_size_percent / 100))
    qr_image = Image.open(qr_buffer).convert('RGBA').resize((qr_size_px, qr_size_px))
    qr_x = round(width * template.qr_code_x_percent / 100)
    qr_y = round(height * template.qr_code_y_percent / 100)
    image.paste(qr_image, (qr_x, qr_y), qr_image)

    output = io.BytesIO()
    image.save(output, format='PDF', resolution=200.0)
    output.seek(0)
    return output.getvalue()
