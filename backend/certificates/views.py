import math
import tempfile
import unicodedata
import zipfile

from django.db.models import Q
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsAdminRole, IsOrgAdminRole, RoleScopedQuerysetMixin

from .models import Certificate, CertificateTemplate
from .permissions import editable_certificate_templates_for_user
from .serializers import AdminCertificateSerializer, CertificateSerializer, CertificateTemplateSerializer
from .services import (
    CertificateIssuanceError,
    _render_certificate_pdf,
    certificate_pdf_uses_current_renderer,
    generate_learning_path_certificate,
)

CERTIFICATE_ZIP_BATCH_SIZE = 25


class AdminCertificatePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = None


def _safe_zip_component(value, limit=100):
    value = unicodedata.normalize('NFC', value or '')
    cleaned = ''.join(
        character if unicodedata.category(character)[0] in ('L', 'M', 'N') or character in '._-' else
        '_' if character.isspace() or character in ',/\\' else ''
        for character in value
    ).strip('._-')
    return cleaned[:limit] or 'unknown'


def _certificate_zip_name(certificate, used_names):
    filename = '_'.join((
        _safe_zip_component(certificate.staff_name, 80),
        _safe_zip_component(certificate.staff_level, 50),
        _safe_zip_component(certificate.certificate_number, 50),
    )) + '.pdf'
    stem, suffix = filename[:-4], '.pdf'
    candidate = filename
    duplicate = 2
    while candidate.casefold() in used_names:
        candidate = f'{stem}_{duplicate}{suffix}'
        duplicate += 1
    used_names.add(candidate.casefold())
    return candidate


class CertificateViewSet(RoleScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Certificate.objects.select_related('user', 'course')
    serializer_class = CertificateSerializer
    org_lookup = 'staff_organization_id'
    owner_lookup = 'user'

    def _admin_queryset(self, request):
        queryset = Certificate.objects.select_related('user', 'course')
        if request.user.role == request.user.Role.ORG_ADMIN:
            if request.user.organization_id is None:
                return queryset.none()
            queryset = queryset.filter(staff_organization_id=request.user.organization_id)
        elif request.user.role == request.user.Role.PLATFORM_ADMIN:
            organization_id = request.query_params.get('organization')
            if organization_id:
                if not organization_id.isdigit():
                    raise ValidationError({'organization': 'Use a valid organization ID.'})
                queryset = queryset.filter(staff_organization_id=int(organization_id))
        else:
            return queryset.none()

        query = request.query_params.get('search', '').strip()
        if query:
            queryset = queryset.filter(
                Q(staff_name__icontains=query) | Q(staff_email__icontains=query)
                | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query)
            )
        sort = request.query_params.get('sort', 'newest')
        if sort == 'name':
            queryset = queryset.order_by(Lower('staff_name'), 'issued_at', 'id')
        elif sort == 'newest':
            queryset = queryset.order_by('-issued_at', '-id')
        else:
            raise ValidationError({'sort': 'Use "newest" or "name".'})
        return queryset

    @action(detail=False, methods=['get'], url_path='admin-list', permission_classes=[IsAuthenticated, IsOrgAdminRole])
    def admin_list(self, request):
        queryset = self._admin_queryset(request)
        paginator = AdminCertificatePagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(AdminCertificateSerializer(page, many=True).data)

    @action(detail=False, methods=['get'], url_path='admin-download-all', permission_classes=[IsAuthenticated, IsOrgAdminRole])
    def admin_download_all(self, request):
        queryset = self._admin_queryset(request)
        count = queryset.count()
        part_count = math.ceil(count / CERTIFICATE_ZIP_BATCH_SIZE)
        try:
            part = int(request.query_params.get('part', '1'))
        except ValueError:
            raise ValidationError({'part': 'Use a valid part number.'})
        if count == 0 or part < 1 or part > part_count:
            raise ValidationError({'part': 'No certificates are available for this ZIP part.'})

        start = (part - 1) * CERTIFICATE_ZIP_BATCH_SIZE
        certificates = queryset[start:start + CERTIFICATE_ZIP_BATCH_SIZE]
        zip_file = tempfile.TemporaryFile()
        used_names = set()
        try:
            with zipfile.ZipFile(zip_file, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
                for certificate in certificates:
                    if not certificate.pdf_file:
                        raise Http404(f'Certificate {certificate.certificate_number} has no PDF.')
                    try:
                        with certificate.pdf_file.open('rb') as stored_pdf:
                            pdf_bytes = stored_pdf.read()
                    except FileNotFoundError:
                        raise Http404(f'Certificate PDF {certificate.certificate_number} is missing.')
                    if not certificate_pdf_uses_current_renderer(pdf_bytes) and certificate.user_id:
                        pdf_bytes = _render_certificate_pdf(certificate)
                    archive.writestr(_certificate_zip_name(certificate, used_names), pdf_bytes)
        except Exception:
            zip_file.close()
            raise

        zip_file.seek(0)
        response = FileResponse(
            zip_file,
            content_type='application/zip',
            as_attachment=True,
            filename=f'certificates-part-{part}-of-{part_count}.zip',
        )
        response['X-Certificate-Zip-Part'] = str(part)
        response['X-Certificate-Zip-Parts'] = str(part_count)
        response['X-Certificate-Zip-Total'] = str(count)
        return response

    @action(detail=False, methods=['post'])
    def issue(self, request):
        """
        Issue (or return the existing) certificate for the caller —
        exactly one per learner, earned by completing their entire
        assigned Learning Path (every course, including its quizzes) and
        passing their assigned Level Assessment. Takes no arguments: there
        is no longer a per-course certificate to ask for. See
        certificates.services.generate_learning_path_certificate.
        """
        try:
            certificate = generate_learning_path_certificate(request.user)
        except CertificateIssuanceError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(CertificateSerializer(certificate, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        certificate = self.get_object()
        if not certificate.pdf_file:
            return Response({'detail': 'No PDF is available for this certificate.'}, status=404)
        try:
            with certificate.pdf_file.open('rb') as stored_pdf:
                pdf_bytes = stored_pdf.read()
        except FileNotFoundError:
            raise Http404('Certificate PDF file is missing.')

        # Certificates issued before the A4/vector renderer was introduced
        # are upgraded in memory when downloaded. The historical database row
        # and stored file remain untouched, while learners immediately receive
        # the corrected printable output.
        if not certificate_pdf_uses_current_renderer(pdf_bytes) and certificate.user_id:
            pdf_bytes = _render_certificate_pdf(certificate)

        # This is an in-memory document, so use a regular HttpResponse.
        # FileResponse asks the WSGI server for a real file descriptor; the
        # production LiteSpeed/LSAPI adapter calls fileno(), which BytesIO
        # deliberately does not implement.
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{certificate.certificate_number}.pdf"'
        return response


class CertificateTemplateViewSet(viewsets.ModelViewSet):
    """
    Admin-only CRUD for branded certificate backgrounds and their calibrated
    text/QR positions — used by the frontend calibration tool. Org-scoped
    same as course content: an ORG_ADMIN/INSTRUCTOR only sees/manages their
    own organization's template; PLATFORM_ADMIN sees every organization's
    plus the platform-level one. See CertificateTemplateSerializer.validate
    for the write-side enforcement of that same boundary.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = CertificateTemplateSerializer

    def get_queryset(self):
        return editable_certificate_templates_for_user(self.request.user).select_related('organization')


# Intentionally public and unauthenticated — this is the link anyone (e.g. an
# employer) can visit to verify a certificate's authenticity by its opaque
# UUID token. Returns only non-sensitive summary fields, never the PDF itself.
def verify_certificate(request, token):
    certificate = Certificate.objects.select_related('user', 'course').filter(verification_token=token).first()

    if certificate is None:
        return JsonResponse({'valid': False, 'detail': 'Certificate not found.'}, status=404)

    is_expired = certificate.expires_at is not None and certificate.expires_at < timezone.now()
    learner_name = certificate.staff_name
    if certificate.user_id:
        learner_name = certificate.user.get_full_name() or certificate.user.email

    return JsonResponse({
        'valid': not is_expired,
        'certificate_number': certificate.certificate_number,
        'course': certificate.course.title,
        'learner_name': learner_name,
        'issued_at': certificate.issued_at.isoformat(),
        'expires_at': certificate.expires_at.isoformat() if certificate.expires_at else None,
    })
