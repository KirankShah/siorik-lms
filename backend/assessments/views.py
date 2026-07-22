from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.permissions import IsAdminRole
from courses.permissions import editable_courses_for_user, visible_courses_for_user

from .models import Choice, Question, Quiz, QuizAnswer, QuizAttempt
from .serializers import (
    ChoiceWriteSerializer,
    QuestionWriteSerializer,
    QuizAttemptSerializer,
    QuizSerializer,
    QuizSubmitSerializer,
    QuizWriteSerializer,
)

WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


class QuizViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Quiz.objects.select_related('page__lesson__module__course').prefetch_related('questions__choices')
    throttle_scope = None  # overridden per-action to 'quiz-submit' on the submit() action below

    def get_permissions(self):
        if self.action in WRITE_ACTIONS:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if self.action in ('retrieve', 'submit'):
            return super().get_queryset().filter(
                page__lesson__module__course__in=visible_courses_for_user(self.request.user)
            )
        return super().get_queryset().filter(
            page__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def get_serializer_class(self):
        if self.action in WRITE_ACTIONS:
            return QuizWriteSerializer
        return QuizSerializer

    def perform_create(self, serializer):
        page = serializer.validated_data['page']
        course = page.lesson.module.course
        if not editable_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'page': 'You do not have permission to modify this course.'})
        serializer.save()

    @action(detail=True, methods=['post'], throttle_classes=[ScopedRateThrottle], throttle_scope='quiz-submit')
    def submit(self, request, pk=None):
        quiz = self.get_object()

        attempts_taken = QuizAttempt.objects.filter(user=request.user, quiz=quiz).count()
        if quiz.max_attempts is not None and attempts_taken >= quiz.max_attempts:
            return Response({'detail': 'Maximum number of attempts reached.'}, status=400)

        serializer = QuizSubmitSerializer(data=request.data, context={'quiz': quiz})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                user=request.user,
                quiz=quiz,
                attempt_number=attempts_taken + 1,
            )
            for answer_data in serializer.validated_data['answers']:
                question = answer_data['question']
                selected_choices = answer_data['selected_choices']
                correct_choice_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
                selected_ids = {choice.id for choice in selected_choices}

                quiz_answer = QuizAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    is_correct=(selected_ids == correct_choice_ids),
                )
                quiz_answer.selected_choices.set(selected_choices)

            attempt.calculate_score_percent()

        return Response(QuizAttemptSerializer(attempt).data, status=201)


class QuestionViewSet(viewsets.ModelViewSet):
    serializer_class = QuestionWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Question.objects.filter(
            quiz__page__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        quiz = serializer.validated_data['quiz']
        course_id = quiz.page.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'quiz': 'You do not have permission to modify this quiz.'})
        serializer.save()


class ChoiceViewSet(viewsets.ModelViewSet):
    serializer_class = ChoiceWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Choice.objects.filter(
            question__quiz__page__lesson__module__course__in=editable_courses_for_user(self.request.user)
        )

    def perform_create(self, serializer):
        question = serializer.validated_data['question']
        course_id = question.quiz.page.lesson.module.course_id
        if not editable_courses_for_user(self.request.user).filter(pk=course_id).exists():
            raise ValidationError({'question': 'You do not have permission to modify this question.'})
        serializer.save()
