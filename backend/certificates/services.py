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
from gamification.services import update_gamification_for_user

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


def certificate_ineligibility_reason(user, course):
    """
    None if `user` is currently eligible for a certificate on `course`;
    otherwise a human-readable reason they aren't (yet). Read-only — never
    creates a Certificate, so it's safe to call speculatively (e.g. to decide
    whether to show a "Retake Course" action) without side effects.

    Eligibility (Phase 34) is exactly two course-wide rules:
    - The Enrollment must be COMPLETED (every slide/lesson done).
    - The learner's AVERAGE score across all of the course's quizzes (each
      quiz's own best attempt) must meet course.certificate_pass_threshold.
      This is a course-wide average, not a requirement that every individual
      quiz independently score at or above its own Quiz.pass_percentage —
      that field remains a per-quiz pass/fail indicator shown to the learner
      during the course, but doesn't itself gate the certificate. A quiz the
      learner has never attempted still blocks issuance (there's no score to
      average in), distinct from one they attempted and failed.
    """
    enrollment = Enrollment.objects.filter(user=user, course=course).first()
    if enrollment is None or enrollment.status != Enrollment.Status.COMPLETED:
        return 'Enrollment must be completed before a certificate can be issued.'

    quizzes = Quiz.objects.filter(slide__lesson__module__course=course)
    best_scores = []
    for quiz in quizzes:
        best = QuizAttempt.objects.filter(user=user, quiz=quiz).aggregate(best=Max('score_percent'))['best']
        if best is None:
            return f'Quiz "{quiz.title}" has not been attempted yet.'
        best_scores.append(best)

    if best_scores:
        average_score = sum(best_scores) / len(best_scores)
        if average_score < course.certificate_pass_threshold:
            return (
                f'Average score {average_score:.1f}% is below the course pass threshold of '
                f'{course.certificate_pass_threshold}%.'
            )
    return None


def generate_certificate(user, course):
    """
    Issue (or return the existing valid) Certificate for a user who has
    completed a course. See certificate_ineligibility_reason for the
    eligibility rules this enforces. Raises CertificateIssuanceError if the
    learner isn't currently eligible.
    """
    reason = certificate_ineligibility_reason(user, course)
    if reason:
        raise CertificateIssuanceError(reason)

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

    update_gamification_for_user(user)
    log_action(user, AuditLog.Action.CERTIFICATE_GENERATED, certificate)
    return certificate


def try_auto_issue_certificate(user, course):
    """
    Best-effort automatic issuance, called right after whichever event just
    changed this user's eligibility for `course` — final slide/lesson
    completion (courses.views.EnrollmentViewSet.slide_progress/complete_lesson)
    or a quiz submission that moves their course-wide average across the
    certificate_pass_threshold (assessments.views.QuizViewSet.submit).
    Either call site may fire before the learner is actually eligible (e.g.
    slides finish before quizzes are attempted) — that's expected, this is a
    silent no-op in that case rather than an error. generate_certificate()
    is itself idempotent (returns the existing certificate if one is still
    valid), so calling this from both events is safe even if both end up
    eligible at once.
    """
    try:
        return generate_certificate(user, course)
    except CertificateIssuanceError:
        return None


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


def _resolve_template(course, user):
    """
    Three-tier fallback: the course's own explicit override, else the
    learner's own organization's template, else the platform-level default —
    see CertificateTemplate's own docstring for the full reasoning.
    """
    template = course.certificate_template
    if template is None and user.organization_id is not None:
        template = CertificateTemplate.objects.filter(organization_id=user.organization_id).first()
    if template is None:
        template = CertificateTemplate.objects.filter(organization__isnull=True, is_default=True).first()
    if template is None:
        raise CertificateIssuanceError(
            'No certificate template is configured for this course or organization, and no platform default '
            'CertificateTemplate exists.'
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
    template = _resolve_template(course, certificate.user)

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
