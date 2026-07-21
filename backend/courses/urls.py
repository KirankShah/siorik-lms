from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CourseViewSet,
    EnrollmentReportView,
    EnrollmentViewSet,
    LessonViewSet,
    ModuleViewSet,
)

router = DefaultRouter()
router.register('courses', CourseViewSet, basename='course')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')
router.register('modules', ModuleViewSet, basename='module')
router.register('lessons', LessonViewSet, basename='lesson')

urlpatterns = router.urls + [
    path('reports/enrollments/', EnrollmentReportView.as_view(), name='enrollment-report'),
]
