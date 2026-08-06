from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import ADMIN_ROLES, IsAdminRole
from courses.models import Enrollment
from courses.permissions import editable_courses_for_user, exclude_demo_locked, is_lesson_locked_for_demo_user, visible_courses_for_user

from .models import MAX_NODES_PER_SLIDE, ScenarioAttempt, ScenarioChoice, ScenarioNode
from .serializers import (
    ScenarioAttemptInputSerializer,
    ScenarioAttemptSerializer,
    ScenarioChoiceWriteSerializer,
    ScenarioNodeSerializer,
    ScenarioNodeWriteSerializer,
)

WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


class ScenarioNodeViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.action in WRITE_ACTIONS:
            return ScenarioNodeWriteSerializer
        return ScenarioNodeSerializer

    def get_permissions(self):
        if self.action in WRITE_ACTIONS:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Read actions (list/retrieve) are how the learner-facing player
        # resolves "the nodes for this slide", so they're scoped to visible
        # (not just editable) courses; writes stay editable-only.
        if self.action in WRITE_ACTIONS:
            courses = editable_courses_for_user(self.request.user)
        else:
            courses = visible_courses_for_user(self.request.user)
        queryset = ScenarioNode.objects.filter(slide__lesson__module__course__in=courses).prefetch_related('choices')
        if self.action not in WRITE_ACTIONS:
            queryset = exclude_demo_locked(queryset, self.request.user, 'slide__lesson')
        slide_id = self.request.query_params.get('slide')
        if slide_id:
            queryset = queryset.filter(slide_id=slide_id)
        return queryset

    def _check_editable(self, slide):
        course = slide.lesson.module.course
        if not editable_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'slide': 'You do not have permission to modify this course.'})

    def perform_create(self, serializer):
        slide = serializer.validated_data['slide']
        self._check_editable(slide)
        if ScenarioNode.objects.filter(slide=slide).count() >= MAX_NODES_PER_SLIDE:
            raise ValidationError({'slide': f'A scenario can have at most {MAX_NODES_PER_SLIDE} nodes.'})
        if serializer.validated_data.get('is_start'):
            ScenarioNode.objects.filter(slide=slide, is_start=True).update(is_start=False)
        serializer.save()

    def perform_update(self, serializer):
        slide = serializer.instance.slide
        self._check_editable(slide)
        if serializer.validated_data.get('is_start'):
            ScenarioNode.objects.filter(slide=slide, is_start=True).exclude(pk=serializer.instance.pk).update(is_start=False)
        serializer.save()


class ScenarioChoiceViewSet(viewsets.ModelViewSet):
    serializer_class = ScenarioChoiceWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return ScenarioChoice.objects.filter(
            node__slide__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        node = serializer.validated_data['node']
        course = node.slide.lesson.module.course
        if not editable_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'node': 'You do not have permission to modify this scenario.'})
        serializer.save()


class ScenarioAttemptViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return ScenarioAttemptInputSerializer
        return ScenarioAttemptSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in ADMIN_ROLES:
            queryset = ScenarioAttempt.objects.filter(
                slide__lesson__module__course__in=editable_courses_for_user(user)
            )
        else:
            queryset = ScenarioAttempt.objects.filter(enrollment__user=user)
        slide_id = self.request.query_params.get('slide')
        if slide_id:
            queryset = queryset.filter(slide_id=slide_id)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slide = serializer.validated_data['slide']
        path_taken = serializer.validated_data['path_taken']

        course = slide.lesson.module.course
        if not visible_courses_for_user(request.user).filter(pk=course.pk).exists():
            raise ValidationError({'slide': 'This scenario is not available to you.'})
        if is_lesson_locked_for_demo_user(request.user, slide.lesson):
            raise ValidationError({'slide': 'This scenario is not available in your demo access.'})
        try:
            enrollment = Enrollment.objects.get(user=request.user, course=course)
        except Enrollment.DoesNotExist:
            raise ValidationError({'slide': 'You are not enrolled in this course.'})

        attempt = ScenarioAttempt.objects.create(
            enrollment=enrollment,
            slide=slide,
            path_taken=[choice.id for choice in path_taken],
            reached_recommended_ending=path_taken[-1].is_recommended,
        )
        return Response(ScenarioAttemptSerializer(attempt).data, status=201)
