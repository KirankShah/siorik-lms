from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.permissions import RoleScopedQuerysetMixin

from .models import Course, Enrollment, Lesson, LessonProgress
from .permissions import visible_courses_for_user
from .serializers import CourseDetailSerializer, CourseListSerializer, EnrollmentSerializer


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'slug'

    def get_queryset(self):
        return visible_courses_for_user(self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        return CourseDetailSerializer


class EnrollmentViewSet(RoleScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Enrollment.objects.select_related('user', 'course')
    serializer_class = EnrollmentSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    org_lookup = 'user__organization'
    owner_lookup = 'user'

    def get_queryset(self):
        queryset = super().get_queryset()
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        if not visible_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'course': 'This course is not available to you.'})
        serializer.save()

    @action(detail=True, methods=['post'], url_path='complete-lesson')
    def complete_lesson(self, request, pk=None):
        enrollment = self.get_object()
        lesson = get_object_or_404(Lesson, pk=request.data.get('lesson'), module__course_id=enrollment.course_id)

        LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
            defaults={'completed_at': timezone.now()},
        )

        total_lessons = Lesson.objects.filter(module__course_id=enrollment.course_id).count()
        completed_lessons = enrollment.lesson_progress.count()
        enrollment.progress_percent = round((completed_lessons / total_lessons) * 100) if total_lessons else 0

        if enrollment.progress_percent >= 100:
            if enrollment.status != Enrollment.Status.COMPLETED:
                enrollment.completed_at = timezone.now()
            enrollment.status = Enrollment.Status.COMPLETED
        elif enrollment.status == Enrollment.Status.NOT_STARTED:
            enrollment.status = Enrollment.Status.IN_PROGRESS

        enrollment.save()
        return Response(EnrollmentSerializer(enrollment).data)
