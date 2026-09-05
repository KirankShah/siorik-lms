from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AssessmentLevelViewSet, LevelAssessmentAttemptViewSet, MyAssessmentLevelView

router = DefaultRouter()
router.register('assessment-levels', AssessmentLevelViewSet, basename='assessment-level')
router.register('level-attempts', LevelAssessmentAttemptViewSet, basename='level-attempt')

urlpatterns = router.urls + [
    path('my-assessment-level/', MyAssessmentLevelView.as_view(), name='my-assessment-level'),
]
