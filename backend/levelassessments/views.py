from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from audit.services import log_action
from core.permissions import IsAdminRole
from gamification.services import award_badges_for_level_assessment_attempt, update_gamification_for_user

from .imports import LevelQuestionImportError, import_level_questions
from .models import LevelAssessmentAttempt
from .permissions import editable_assessment_levels_for_user
from .serializers import AssessmentLevelSerializer, LevelAssessmentAttemptSerializer, LevelAssessmentSubmitSerializer
from .services import LevelAssessmentError, assigned_assessment_level_for_user, start_level_assessment_attempt


class AssessmentLevelViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only for now (AssessmentLevel/QuestionSet authoring itself isn't
    exposed here yet) — list/retrieve exist so an admin can pick which level
    to import questions into. Admin-only, org-scoped same as course content:
    an ORG_ADMIN/INSTRUCTOR only sees/imports into their own organization's
    levels; PLATFORM_ADMIN sees every organization's.
    """

    serializer_class = AssessmentLevelSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return editable_assessment_levels_for_user(self.request.user).select_related('organization')

    @action(detail=True, methods=['post'], url_path='import-questions')
    def import_questions(self, request, pk=None):
        """
        Admin-only bulk import of LevelQuestion/LevelChoice rows from an
        uploaded Level Assessment Question Template (.xlsx) into this
        AssessmentLevel. See levelassessments.imports.import_level_questions
        for the per-row validation/reporting contract.
        """
        assessment_level = self.get_object()

        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'An .xlsx file is required (field name "file").'}, status=400)

        try:
            created, failed = import_level_questions(assessment_level=assessment_level, workbook_file=upload)
        except LevelQuestionImportError as exc:
            return Response({'detail': str(exc)}, status=400)

        if created:
            log_action(request.user, AuditLog.Action.LEVEL_QUESTIONS_IMPORTED, assessment_level)

        return Response({'created': created, 'failed': failed})


class MyAssessmentLevelView(APIView):
    """
    Learner-facing "what am I assigned, and where do I stand" lookup — backs
    the dashboard widget and the assessment landing screen. Derives the
    assessment level from the caller's own organization + assessment_level
    field (see accounts.models.User), never from a client-supplied id, so a
    user can't probe another organization's levels by guessing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        assessment_level = assigned_assessment_level_for_user(request.user)
        if assessment_level is None:
            return Response({'assigned': False})

        open_attempt = LevelAssessmentAttempt.objects.filter(
            user=request.user, assessment_level=assessment_level, submitted_at__isnull=True
        ).first()

        if open_attempt is not None:
            status_value = 'IN_PROGRESS'
        else:
            latest_attempt = (
                LevelAssessmentAttempt.objects.filter(
                    user=request.user, assessment_level=assessment_level, submitted_at__isnull=False
                )
                .order_by('-submitted_at')
                .first()
            )
            if latest_attempt is None:
                status_value = 'NOT_STARTED'
            else:
                status_value = 'PASSED' if latest_attempt.passed else 'FAILED'

        return Response({
            'assigned': True,
            'assessment_level': AssessmentLevelSerializer(assessment_level, context={'request': request}).data,
            'status': status_value,
            'open_attempt_id': open_attempt.id if open_attempt else None,
        })


class LevelAssessmentAttemptViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Learner-facing attempt lifecycle: start a fresh attempt, retrieve one to
    resume/review it, submit answers for grading. Scoped to the caller's own
    attempts only — there's no admin/instructor browsing surface here.
    """

    serializer_class = LevelAssessmentAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LevelAssessmentAttempt.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def start(self, request):
        assessment_level = assigned_assessment_level_for_user(request.user)
        if assessment_level is None:
            return Response({'detail': 'You do not have an assigned assessment level.'}, status=400)

        try:
            attempt = start_level_assessment_attempt(user=request.user, assessment_level=assessment_level)
        except LevelAssessmentError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(LevelAssessmentAttemptSerializer(attempt, context={'request': request}).data, status=201)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        attempt = self.get_object()
        if attempt.submitted_at is not None:
            return Response({'detail': 'This attempt has already been submitted.'}, status=400)

        serializer = LevelAssessmentSubmitSerializer(data=request.data, context={'attempt': attempt})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            for answer_data in serializer.validated_data['answers']:
                question = answer_data['question']
                selected_choices = answer_data['selected_choices']
                correct_choice_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
                selected_ids = {choice.id for choice in selected_choices}
                is_correct = selected_ids == correct_choice_ids

                answer = attempt.answers.create(question=question, is_correct=is_correct)
                answer.selected_choices.set(selected_choices)

            attempt.calculate_score_percent()
            # Same trigger point as course completion/quiz attempt — keeps
            # LeaderboardEntry.total_points (and level_assessments_passed_count)
            # in sync with this attempt's outcome immediately.
            update_gamification_for_user(request.user)
            award_badges_for_level_assessment_attempt(attempt)

        return Response(LevelAssessmentAttemptSerializer(attempt, context={'request': request}).data)
