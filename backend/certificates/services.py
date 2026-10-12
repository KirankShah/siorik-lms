import hashlib
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
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from assessments.models import Quiz, QuizAttempt
from audit.models import AuditLog
from audit.services import log_action
from courses.models import Enrollment
from gamification.services import update_gamification_for_user
from org_settings.models import pass_mark_percent_for_user

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
PDF_PAGE_SIZE = landscape(A4)
DEFAULT_PDF_FONT = 'Helvetica'
# Bump this marker whenever a production template upgrade must also apply to
# PDFs already stored by an earlier renderer. The download endpoint rebuilds
# any PDF whose marker differs, so existing learners receive the 300-DPI
# branded template without mutating their certificate record.
PDF_RENDERER_MARKER = 'siorik-certificate-renderer-v3'


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
      quiz's own best attempt) must meet `user`'s own organization's
      org_settings.OrganizationSettings.pass_mark_percent — the same
      org-wide value every course now shares (previously a per-course
      Course.certificate_pass_threshold field). This is a course-wide
      average. Individual quiz attempts use this same organization-wide mark,
      while certificate eligibility applies it to the overall quiz average.
      A quiz the learner has never attempted still blocks issuance (there's
      no score to average in), distinct from one they attempted and failed.
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
        pass_mark_percent = pass_mark_percent_for_user(user)
        if average_score < pass_mark_percent:
            return (
                f'Average score {average_score:.1f}% is below the course pass threshold of '
                f'{pass_mark_percent}%.'
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


LEARNING_PATH_CERTIFICATE_TITLE = 'Certificate of Competency in AML/CFT and Financial Crime Compliance'


def _learning_path_completion_title(user):
    """
    Display text for the certificate's "course name" field — under the
    current policy there's only ever ONE certificate per learner, issued
    for finishing their entire Learning Path, not any single course. Fixed
    and identical for every learner regardless of assessment level/tier —
    not the course's title, and not a per-tier variant (see
    generate_learning_path_certificate — the underlying Certificate row
    still points at a real course, for template-resolution and
    record-keeping, but that's not what gets drawn here).
    """
    return LEARNING_PATH_CERTIFICATE_TITLE


def learning_path_certificate_ineligibility_reason(user):
    """
    None if `user` is eligible for their Learning Path Completion
    Certificate — the ONLY certificate issued under the current policy; a
    learner is never issued a separate certificate per course. Otherwise a
    human-readable reason they aren't (yet).

    Eligibility:
    - The learner must have a Learning Path assigned at all (at least one
      path_order'd course visible to them — see
      courses.learning_path.build_learning_path).
    - Every course in that path (Foundation, plus their assigned tier if
      any) must be completed AND meet ITS OWN quiz-average threshold —
      reuses certificate_ineligibility_reason per course rather than
      re-deriving that math.
    - If the learner has an assigned assessment tier, they must have
      PASSED that tier's Level Assessment — the same gate that already
      unlocks the tier itself (courses.learning_path.has_passed_tier_assessment).
    """
    from courses.learning_path import build_learning_path, has_passed_tier_assessment
    from courses.models import Course

    path = build_learning_path(user)
    all_path_courses = [course for tier in path['tiers'] for course in tier['courses']]
    if not all_path_courses:
        return 'No Learning Path has been assigned yet.'

    for course_row in all_path_courses:
        if course_row['state'] != 'completed':
            return f'"{course_row["title"]}" has not been completed yet.'
        reason = certificate_ineligibility_reason(user, Course.objects.get(pk=course_row['id']))
        if reason:
            return f'"{course_row["title"]}": {reason}'

    if user.assessment_level and not has_passed_tier_assessment(user, user.assessment_level):
        return 'The assigned Level Assessment has not been passed yet.'

    return None


def generate_learning_path_certificate(user):
    """
    Issues (or returns the existing) certificate for completing `user`'s
    entire Learning Path — see learning_path_certificate_ineligibility_reason
    for the full eligibility rule this enforces. Anchored to the last
    course in their path (by path_order) purely for template-resolution
    and record-keeping — reuses the existing generate_certificate(user,
    course) machinery unchanged (same idempotency, same PDF rendering),
    just always called with that one course and gated by the stricter
    whole-path rule above instead of that single course's own eligibility.
    """
    from courses.learning_path import build_learning_path
    from courses.models import Course

    reason = learning_path_certificate_ineligibility_reason(user)
    if reason:
        raise CertificateIssuanceError(reason)

    path = build_learning_path(user)
    all_path_courses = [c for tier in path['tiers'] for c in tier['courses']]
    finale_course = Course.objects.get(pk=max(all_path_courses, key=lambda c: c['path_order'])['id'])
    return generate_certificate(user, finale_course)


def try_issue_learning_path_certificate(user):
    """
    Best-effort issuance of the single Learning Path Completion
    Certificate, called right after any event that could newly satisfy
    eligibility: a course completing (courses.views.EnrollmentViewSet.
    slide_progress/complete_lesson), a quiz submission crossing the
    learner's own organization's pass_mark_percent (assessments.views.
    QuizViewSet.submit), or a level assessment attempt being passed
    (levelassessments.views).
    Any of these may fire well before the learner is actually eligible
    (most of their path isn't done yet) — that's expected, this is a
    silent no-op in that case. generate_learning_path_certificate() is
    itself idempotent, so calling this from every contributing event is
    safe even if more than one ends up newly eligible at once.
    """
    try:
        return generate_learning_path_certificate(user)
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


def _register_pdf_font(font_file):
    """Return a ReportLab font name for an uploaded TTF, or a safe built-in fallback."""
    if not font_file:
        logger.warning('CertificateTemplate field has no font_file configured; rendering with Helvetica.')
        return DEFAULT_PDF_FONT

    font_bytes = _read_field_bytes(font_file)
    font_name = f'CertificateFont_{hashlib.sha256(font_bytes).hexdigest()[:16]}'
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, io.BytesIO(font_bytes)))
    return font_name


def _fit_pdf_font_size(font_name, initial_size_px, text, max_width_points, points_per_pixel):
    """Scale a calibrated pixel font size to the PDF and shrink it to the safe area."""
    size_px = initial_size_px
    size_points = size_px * points_per_pixel
    while size_px > MIN_AUTO_SHRINK_FONT_SIZE:
        if pdfmetrics.stringWidth(text, font_name, size_points) <= max_width_points:
            break
        size_px -= 2
        size_points = size_px * points_per_pixel
    return size_points


def _draw_pdf_field(pdf, image_box, text, x_percent, y_percent, font_name, font_size, text_align, color):
    """Draw a calibrated field using the template's top-left percentage coordinate system."""
    image_x, image_y, image_width, image_height = image_box
    x = image_x + image_width * x_percent / 100
    y_mid = image_y + image_height * (1 - y_percent / 100)

    ascent, descent = pdfmetrics.getAscentDescent(font_name, font_size)
    baseline_y = y_mid - (ascent + descent) / 2

    pdf.setFillColor(HexColor(color))
    pdf.setFont(font_name, font_size)
    if text_align == CertificateTemplate.TextAlign.LEFT:
        pdf.drawString(x, baseline_y, text)
    elif text_align == CertificateTemplate.TextAlign.RIGHT:
        pdf.drawRightString(x, baseline_y, text)
    else:
        pdf.drawCentredString(x, baseline_y, text)


def _render_certificate_pdf(certificate):
    course = certificate.course
    template = _resolve_template(course, certificate.user)

    background_bytes = _read_field_bytes(template.background_image)
    with Image.open(io.BytesIO(background_bytes)) as background:
        source_width, source_height = background.size

    page_width, page_height = PDF_PAGE_SIZE
    scale = min(page_width / source_width, page_height / source_height)
    image_width = source_width * scale
    image_height = source_height * scale
    image_x = (page_width - image_width) / 2
    image_y = (page_height - image_height) / 2
    image_box = (image_x, image_y, image_width, image_height)
    max_text_width_points = image_width * (1 - 2 * TEXT_SAFE_MARGIN_PERCENT / 100)

    learner_name = certificate.user.get_full_name() or certificate.user.email
    completion_date = certificate.issued_at.strftime('%B %d, %Y')

    staff_name_font = _register_pdf_font(template.staff_name_font_file)
    staff_name_font_size = _fit_pdf_font_size(
        staff_name_font, template.staff_name_font_size, learner_name, max_text_width_points, scale
    )

    # Not course.title — see _learning_path_completion_title: this
    # certificate represents finishing the whole Learning Path, not this
    # one (anchor) course.
    course_name_text = _learning_path_completion_title(certificate.user)
    course_name_font = _register_pdf_font(template.course_name_font_file)
    course_name_font_size = _fit_pdf_font_size(
        course_name_font, template.course_name_font_size, course_name_text, max_text_width_points, scale
    )

    issue_date_font = _register_pdf_font(template.issue_date_font_file)
    issue_date_font_size = template.issue_date_font_size * scale

    qr_buffer = io.BytesIO()
    qrcode.make(_build_verification_url(certificate.verification_token)).save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=PDF_PAGE_SIZE, pageCompression=1)
    pdf.setKeywords(PDF_RENDERER_MARKER)
    pdf.drawImage(
        ImageReader(io.BytesIO(background_bytes)), image_x, image_y,
        width=image_width, height=image_height, preserveAspectRatio=True, mask='auto',
    )

    _draw_pdf_field(
        pdf, image_box, learner_name,
        template.staff_name_x_percent, template.staff_name_y_percent,
        staff_name_font, staff_name_font_size, template.staff_name_text_align, template.staff_name_color,
    )
    _draw_pdf_field(
        pdf, image_box, course_name_text,
        template.course_name_x_percent, template.course_name_y_percent,
        course_name_font, course_name_font_size, template.course_name_text_align, template.course_name_color,
    )
    _draw_pdf_field(
        pdf, image_box, completion_date,
        template.issue_date_x_percent, template.issue_date_y_percent,
        issue_date_font, issue_date_font_size, template.issue_date_text_align, template.issue_date_color,
    )

    # QR positions are stored as top-left percentages, matching the calibration
    # rectangle in the admin preview. ReportLab uses a bottom-left origin.
    qr_size = max(1, image_width * template.qr_code_size_percent / 100)
    qr_x = image_x + image_width * template.qr_code_x_percent / 100
    qr_y = image_y + image_height * (1 - template.qr_code_y_percent / 100) - qr_size
    pdf.drawImage(ImageReader(qr_buffer), qr_x, qr_y, width=qr_size, height=qr_size, mask='auto')

    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output.getvalue()


def certificate_pdf_uses_current_renderer(pdf_bytes):
    """Identify PDFs produced by the high-quality A4 renderer."""
    return PDF_RENDERER_MARKER.encode('ascii') in pdf_bytes
