from rest_framework.routers import DefaultRouter

from .views import AssignmentSubmissionViewSet, AssignmentViewSet

router = DefaultRouter()
router.register('assignments', AssignmentViewSet, basename='assignment')
router.register('assignment-submissions', AssignmentSubmissionViewSet, basename='assignment-submission')

urlpatterns = router.urls
