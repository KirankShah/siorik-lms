from rest_framework.routers import DefaultRouter

from .views import DemoUserViewSet, OrganizationViewSet

router = DefaultRouter()
router.register('organizations', OrganizationViewSet, basename='organization')
router.register('demo-users', DemoUserViewSet, basename='demo-user')

urlpatterns = router.urls
