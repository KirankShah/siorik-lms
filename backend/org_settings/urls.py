from rest_framework.routers import DefaultRouter

from .views import OrganizationSettingsViewSet

router = DefaultRouter()
router.register('organization-settings', OrganizationSettingsViewSet, basename='organization-settings')

urlpatterns = router.urls
