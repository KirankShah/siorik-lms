import io

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from assessments.models import Quiz, QuizAttempt
from courses.models import Enrollment

from .models import Certificate


class CertificateIssuanceError(Exception):
    """Raised when a certificate cannot be issued for a user/course combination."""


def generate_certificate(user, course):
    """
    Issue (or return the existing valid) Certificate for a user who has completed a course.

    Requires the user's Enrollment to be COMPLETED, and every Quiz linked to the
    course to have at least one passed QuizAttempt by the user. Raises
    CertificateIssuanceError if either condition is not met.
    """
    enrollment = Enrollment.objects.filter(user=user, course=course).first()
    if enrollment is None or enrollment.status != Enrollment.Status.COMPLETED:
        raise CertificateIssuanceError('Enrollment must be completed before a certificate can be issued.')

    for quiz in Quiz.objects.filter(course=course):
        if not QuizAttempt.objects.filter(user=user, quiz=quiz, passed=True).exists():
            raise CertificateIssuanceError(f'Quiz "{quiz.title}" has not been passed yet.')

    existing = Certificate.objects.filter(user=user, course=course).order_by('-issued_at').first()
    if existing and (existing.expires_at is None or existing.expires_at > timezone.now()):
        return existing

    with transaction.atomic():
        certificate = Certificate.objects.create(
            user=user,
            course=course,
            certificate_number=_generate_certificate_number(),
        )
        pdf_bytes = _render_certificate_pdf(certificate)
        certificate.pdf_file.save(f'{certificate.certificate_number}.pdf', ContentFile(pdf_bytes), save=True)

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


def _render_certificate_pdf(certificate):
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    qr_buffer = io.BytesIO()
    qrcode.make(_build_verification_url(certificate.verification_token)).save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    learner_name = certificate.user.get_full_name() or certificate.user.email
    completion_date = certificate.issued_at.strftime('%B %d, %Y')

    page.setFont('Helvetica-Bold', 28)
    page.drawCentredString(width / 2, height - 4 * cm, 'Certificate of Completion')

    page.setFont('Helvetica', 16)
    page.drawCentredString(width / 2, height - 6 * cm, 'This certifies that')

    page.setFont('Helvetica-Bold', 22)
    page.drawCentredString(width / 2, height - 7.5 * cm, learner_name)

    page.setFont('Helvetica', 16)
    page.drawCentredString(width / 2, height - 9 * cm, 'has successfully completed')

    page.setFont('Helvetica-Bold', 20)
    page.drawCentredString(width / 2, height - 10.5 * cm, certificate.course.title)

    page.setFont('Helvetica', 14)
    page.drawCentredString(width / 2, height - 12.5 * cm, f'Completion date: {completion_date}')
    page.drawCentredString(width / 2, height - 13.5 * cm, f'Certificate No: {certificate.certificate_number}')

    page.drawImage(
        ImageReader(qr_buffer),
        width - 6 * cm,
        2 * cm,
        width=4 * cm,
        height=4 * cm,
    )
    page.setFont('Helvetica', 8)
    page.drawCentredString(width - 4 * cm, 1.7 * cm, 'Scan to verify')

    page.showPage()
    page.save()
    buffer.seek(0)
    return buffer.getvalue()
