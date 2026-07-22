from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CourseViewSet,
    EnrollmentReportView,
    EnrollmentViewSet,
    LessonViewSet,
    MediaUploadView,
    ModuleViewSet,
    PageViewSet,
)

router = DefaultRouter()
router.register('courses', CourseViewSet, basename='course')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')
router.register('modules', ModuleViewSet, basename='module')
router.register('lessons', LessonViewSet, basename='lesson')
router.register('pages', PageViewSet, basename='page')

urlpatterns = router.urls + [
    path('reports/enrollments/', EnrollmentReportView.as_view(), name='enrollment-report'),
    path('media/upload/', MediaUploadView.as_view(), name='media-upload'),
]
