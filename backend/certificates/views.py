from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsAdminRole, RoleScopedQuerysetMixin

from .models import Certificate, CertificateTemplate
from .permissions import editable_certificate_templates_for_user
from .serializers import CertificateSerializer, CertificateTemplateSerializer
from .services import CertificateIssuanceError, generate_learning_path_certificate


class CertificateViewSet(RoleScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Certificate.objects.select_related('user', 'course')
    serializer_class = CertificateSerializer
    org_lookup = 'user__organization'
    owner_lookup = 'user'

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
            file_handle = certificate.pdf_file.open('rb')
        except FileNotFoundError:
            raise Http404('Certificate PDF file is missing.')
        return FileResponse(
            file_handle,
            content_type='application/pdf',
            as_attachment=True,
            filename=f'{certificate.certificate_number}.pdf',
        )


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

    return JsonResponse({
        'valid': not is_expired,
        'certificate_number': certificate.certificate_number,
        'course': certificate.course.title,
        'learner_name': certificate.user.get_full_name() or certificate.user.email,
        'issued_at': certificate.issued_at.isoformat(),
        'expires_at': certificate.expires_at.isoformat() if certificate.expires_at else None,
    })
