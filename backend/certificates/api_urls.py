from rest_framework.routers import DefaultRouter

from .views import CertificateTemplateViewSet, CertificateViewSet

router = DefaultRouter()
router.register('certificates', CertificateViewSet, basename='certificate')
router.register('certificate-templates', CertificateTemplateViewSet, basename='certificate-template')

urlpatterns = router.urls
