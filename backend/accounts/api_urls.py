from rest_framework.routers import DefaultRouter

from .views import DemoUserViewSet, OrgAdminViewSet, OrganizationViewSet

router = DefaultRouter()
router.register('organizations', OrganizationViewSet, basename='organization')
router.register('demo-users', DemoUserViewSet, basename='demo-user')
router.register('org-admins', OrgAdminViewSet, basename='org-admin')

urlpatterns = router.urls
