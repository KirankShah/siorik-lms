from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from core.permissions import RoleScopedQuerysetMixin

from .models import Course, Enrollment
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

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        if not visible_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'course': 'This course is not available to you.'})
        serializer.save()
