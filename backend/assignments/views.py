from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.permissions import ADMIN_ROLES, IsAdminRole
from courses.permissions import editable_courses_for_user, visible_courses_for_user

from .models import Assignment, AssignmentSubmission
from .serializers import AssignmentSerializer, AssignmentSubmissionCreateSerializer, AssignmentSubmissionSerializer


class AssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = Assignment.objects.filter(
            page__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )
        page_id = self.request.query_params.get('page')
        if page_id:
            queryset = queryset.filter(page_id=page_id)
        return queryset

    def perform_create(self, serializer):
        page = serializer.validated_data['page']
        course = page.lesson.module.course
        if not editable_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'page': 'You do not have permission to modify this course.'})
        serializer.save()


class AssignmentSubmissionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Two audiences share this endpoint: instructors listing/grading submissions
    (scoped to courses they can edit), and learners creating their own and
    checking on them (scoped to their own rows). Grading (update) stays
    admin-only.
    """

    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('update', 'partial_update'):
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return AssignmentSubmissionCreateSerializer
        return AssignmentSubmissionSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in ADMIN_ROLES:
            queryset = AssignmentSubmission.objects.filter(
                assignment__page__lesson__module__course__in=editable_courses_for_user(user)
            )
        else:
            queryset = AssignmentSubmission.objects.filter(user=user)
        queryset = queryset.select_related('assignment', 'assignment__page', 'user')

        assignment_id = self.request.query_params.get('assignment')
        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)
        if self.request.query_params.get('ungraded') == 'true':
            queryset = queryset.filter(marks_awarded__isnull=True)
        return queryset

    def perform_create(self, serializer):
        assignment = serializer.validated_data['assignment']
        course = assignment.page.lesson.module.course
        if not visible_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'assignment': 'This assignment is not available to you.'})
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(graded_at=timezone.now())
