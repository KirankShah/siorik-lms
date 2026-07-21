from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import RoleScopedQuerysetMixin

from .models import Certificate
from .serializers import CertificateSerializer


class CertificateViewSet(RoleScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Certificate.objects.select_related('user', 'course')
    serializer_class = CertificateSerializer
    org_lookup = 'user__organization'
    owner_lookup = 'user'

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
