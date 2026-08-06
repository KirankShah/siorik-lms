from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.permissions import ADMIN_ROLES, IsAdminRole
from courses.permissions import editable_courses_for_user, exclude_demo_locked, is_lesson_locked_for_demo_user, visible_courses_for_user

from .models import Assignment, AssignmentSubmission
from .serializers import AssignmentSerializer, AssignmentSubmissionCreateSerializer, AssignmentSubmissionSerializer


WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


class AssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssignmentSerializer

    def get_permissions(self):
        if self.action in WRITE_ACTIONS:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Read actions (list/retrieve) are how the learner-facing player
        # resolves "the assignment for this slide", so they're scoped to
        # visible (not just editable) courses; writes stay editable-only.
        if self.action in WRITE_ACTIONS:
            courses = editable_courses_for_user(self.request.user)
        else:
            courses = visible_courses_for_user(self.request.user)
        queryset = Assignment.objects.filter(slide__lesson__module__course__in=courses)
        if self.action not in WRITE_ACTIONS:
            queryset = exclude_demo_locked(queryset, self.request.user, 'slide__lesson')
        slide_id = self.request.query_params.get('slide')
        if slide_id:
            queryset = queryset.filter(slide_id=slide_id)
        return queryset

    def perform_create(self, serializer):
        slide = serializer.validated_data['slide']
        course = slide.lesson.module.course
        if not editable_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'slide': 'You do not have permission to modify this course.'})
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
                assignment__slide__lesson__module__course__in=editable_courses_for_user(user)
            )
        else:
            queryset = AssignmentSubmission.objects.filter(user=user)
        queryset = queryset.select_related('assignment', 'assignment__slide', 'user')

        assignment_id = self.request.query_params.get('assignment')
        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)
        if self.request.query_params.get('ungraded') == 'true':
            queryset = queryset.filter(marks_awarded__isnull=True)
        return queryset

    def perform_create(self, serializer):
        assignment = serializer.validated_data['assignment']
        course = assignment.slide.lesson.module.course
        if not visible_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'assignment': 'This assignment is not available to you.'})
        if is_lesson_locked_for_demo_user(self.request.user, assignment.slide.lesson):
            raise ValidationError({'assignment': 'This assignment is not available in your demo access.'})
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(graded_at=timezone.now())
