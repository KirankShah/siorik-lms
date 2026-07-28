from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CourseViewSet,
    ElementViewSet,
    EnrollmentReportView,
    EnrollmentViewSet,
    LessonViewSet,
    MediaUploadView,
    ModuleViewSet,
    SlideViewSet,
)

router = DefaultRouter()
router.register('courses', CourseViewSet, basename='course')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')
router.register('modules', ModuleViewSet, basename='module')
router.register('lessons', LessonViewSet, basename='lesson')
router.register('slides', SlideViewSet, basename='slide')
router.register('elements', ElementViewSet, basename='element')

urlpatterns = router.urls + [
    path('reports/enrollments/', EnrollmentReportView.as_view(), name='enrollment-report'),
    path('media/upload/', MediaUploadView.as_view(), name='media-upload'),
]
