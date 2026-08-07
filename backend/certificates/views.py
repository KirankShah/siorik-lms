from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsAdminRole, RoleScopedQuerysetMixin
from courses.permissions import visible_courses_for_user

from .models import Certificate, CertificateTemplate
from .serializers import CertificateSerializer, CertificateTemplateSerializer
from .services import CertificateIssuanceError, generate_certificate


class CertificateViewSet(RoleScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Certificate.objects.select_related('user', 'course')
    serializer_class = CertificateSerializer
    org_lookup = 'user__organization'
    owner_lookup = 'user'

    @action(detail=False, methods=['post'])
    def issue(self, request):
        """Issue (or return the existing valid) certificate for the caller on a given course."""
        course = get_object_or_404(visible_courses_for_user(request.user), pk=request.data.get('course'))
        try:
            certificate = generate_certificate(request.user, course)
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
    text/QR positions — used by the frontend calibration tool. Not org-scoped:
    templates are shared platform-wide branding assets, same as SlideTemplate.
    """

    permission_classes = [IsAdminRole]
    queryset = CertificateTemplate.objects.all()
    serializer_class = CertificateTemplateSerializer


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
