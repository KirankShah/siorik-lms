from django.urls import path
from rest_framework.routers import DefaultRouter

from .video_streaming import stream_element_video
from .views import (
    AdminAnalyticsView,
    CourseViewSet,
    ElementViewSet,
    EnrollmentReportView,
    EnrollmentViewSet,
    LearnerRosterView,
    LearningPathView,
    LessonViewSet,
    LevelCourseAssignmentDetailView,
    LevelCourseAssignmentListView,
    LevelCourseAssignmentReorderView,
    MediaUploadView,
    ModuleViewSet,
    SlideTemplateViewSet,
    SlideViewSet,
    StaffTrainingReportView,
)

router = DefaultRouter()
router.register('courses', CourseViewSet, basename='course')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')
router.register('modules', ModuleViewSet, basename='module')
router.register('lessons', LessonViewSet, basename='lesson')
router.register('slides', SlideViewSet, basename='slide')
router.register('elements', ElementViewSet, basename='element')
router.register('slide-templates', SlideTemplateViewSet, basename='slide-template')

urlpatterns = router.urls + [
    path('learning-path/', LearningPathView.as_view(), name='learning-path'),
    path('level-course-assignments/', LevelCourseAssignmentListView.as_view(), name='level-course-assignment-list'),
    path(
        'level-course-assignments/reorder/',
        LevelCourseAssignmentReorderView.as_view(),
        name='level-course-assignment-reorder',
    ),
    path(
        'level-course-assignments/<int:pk>/',
        LevelCourseAssignmentDetailView.as_view(),
        name='level-course-assignment-detail',
    ),
    path('reports/enrollments/', EnrollmentReportView.as_view(), name='enrollment-report'),
    path('reports/learners/', LearnerRosterView.as_view(), name='learner-roster'),
    path('reports/analytics/', AdminAnalyticsView.as_view(), name='admin-analytics'),
    path('reports/staff-training/', StaffTrainingReportView.as_view(), name='staff-training-report'),
    path('media/upload/', MediaUploadView.as_view(), name='media-upload'),
    path('elements/<int:pk>/video/', stream_element_video, name='element-video-stream'),
]
