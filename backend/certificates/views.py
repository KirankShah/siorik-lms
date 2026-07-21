from django.http import JsonResponse
from django.utils import timezone

from .models import Certificate


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
