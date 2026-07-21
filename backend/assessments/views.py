from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from courses.permissions import visible_courses_for_user

from .models import Quiz, QuizAnswer, QuizAttempt
from .serializers import QuizAttemptSerializer, QuizSerializer, QuizSubmitSerializer


class QuizViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = QuizSerializer
    queryset = Quiz.objects.select_related('course').prefetch_related('questions__choices')

    def get_queryset(self):
        visible_courses = visible_courses_for_user(self.request.user)
        return super().get_queryset().filter(course__in=visible_courses)

    @action(detail=True, methods=['post'])
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
