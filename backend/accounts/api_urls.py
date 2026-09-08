from rest_framework.routers import DefaultRouter

from .views import (
    DemoUserViewSet,
    LearnerViewSet,
    OrgAdminViewSet,
    OrganizationViewSet,
    StaffEnrollmentViewSet,
)

router = DefaultRouter()
router.register('organizations', OrganizationViewSet, basename='organization')
router.register('demo-users', DemoUserViewSet, basename='demo-user')
router.register('org-admins', OrgAdminViewSet, basename='org-admin')
router.register('learners', LearnerViewSet, basename='learner')
router.register('staff', StaffEnrollmentViewSet, basename='staff')

urlpatterns = router.urls
