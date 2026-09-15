from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from audit.services import log_action
from core.permissions import IsAdminRole

from .imports import LevelQuestionImportError, import_level_questions
from .models import LevelAssessmentAttempt
from .permissions import editable_assessment_levels_for_user
from .serializers import (
    AssessmentLevelSerializer,
    LevelAssessmentAdvanceSerializer,
    LevelAssessmentAnswerInputSerializer,
    LevelAssessmentAttemptSerializer,
    LevelAssessmentSubmitSerializer,
)
from .services import (
    LevelAssessmentError,
    advance_level_assessment_attempt,
    assigned_assessment_level_for_user,
    finalize_level_assessment_attempt,
    level_assessment_attempts_remaining,
    resume_level_assessment_attempt,
    save_level_assessment_answer_progress,
    start_level_assessment_attempt,
)


class AssessmentLevelViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only: list/retrieve so an admin can pick which level to import
    questions into (the four tiers themselves are fixed — seeded per
    organization). Pass mark / questions-per-attempt / seconds-per-question
    are edited from the Organization Settings screen (org_settings app), not
    per level here — see AssessmentLevelSerializer. Admin-only, org-scoped
    same as course content: an ORG_ADMIN/INSTRUCTOR only sees their own
    organization's levels; PLATFORM_ADMIN sees every organization's.
    """

    serializer_class = AssessmentLevelSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    http_method_names = ['get', 'head', 'options', 'post']  # post is the import-questions @action below

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
            # None = unlimited (org's max_level_assessment_attempts unset) —
            # lets the frontend disable/explain the retake action itself
            # before the learner even tries, not just after a 400 from start.
            'attempts_remaining': level_assessment_attempts_remaining(request.user, assessment_level),
        })


class LevelAssessmentAttemptViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Learner-facing attempt lifecycle: start a fresh attempt, retrieve one to
    resume it (which also runs the away-time catch-up — see
    resume_level_assessment_attempt), record progress as the learner answers
    and advances, and submit for grading. Scoped to the caller's own
    attempts only — there's no admin/instructor browsing surface here.
    """

    serializer_class = LevelAssessmentAttemptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LevelAssessmentAttempt.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        attempt = self.get_object()
        if attempt.submitted_at is None:
            # Applies whatever auto-advance/auto-submit would have happened
            # live, based on real elapsed time since the current timer
            # segment began — see the function's own docstring. A no-op
            # (besides this read) if nothing has actually expired.
            attempt = resume_level_assessment_attempt(attempt)
        serializer = self.get_serializer(attempt)
        return Response(serializer.data)

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

    @action(detail=True, methods=['post'], url_path='save-answer')
    def save_answer(self, request, pk=None):
        """
        Persists the learner's current selection for one question into the
        attempt's answers_so_far scratch-pad — called on every answer change
        during a live attempt (not just when moving on), so a crash
        mid-selection still resumes with that selection intact. Never
        touches current_question_index or the timer — see `advance` for that.
        """
        attempt = self.get_object()
        if attempt.submitted_at is not None:
            return Response({'detail': 'This attempt has already been submitted.'}, status=400)

        serializer = LevelAssessmentAnswerInputSerializer(data=request.data, context={'attempt': attempt})
        serializer.is_valid(raise_exception=True)

        save_level_assessment_answer_progress(
            attempt,
            question=serializer.validated_data['question'],
            selected_choice_ids=[choice.id for choice in serializer.validated_data['selected_choices']],
        )
        return Response(LevelAssessmentAttemptSerializer(attempt, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def advance(self, request, pk=None):
        """
        Moves the attempt on to the next question — called right before the
        frontend locally advances, whether by the learner clicking Next or a
        PER_QUESTION timeout auto-advancing, so the server always knows
        exactly where the learner is (needed for resume — see
        resume_level_assessment_attempt) and, under PER_QUESTION timing,
        resets the new question's own countdown.
        """
        attempt = self.get_object()
        if attempt.submitted_at is not None:
            return Response({'detail': 'This attempt has already been submitted.'}, status=400)

        serializer = LevelAssessmentAdvanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            advance_level_assessment_attempt(attempt, new_index=serializer.validated_data['current_question_index'])
        except LevelAssessmentError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(LevelAssessmentAttemptSerializer(attempt, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        attempt = self.get_object()
        if attempt.submitted_at is not None:
            return Response({'detail': 'This attempt has already been submitted.'}, status=400)

        serializer = LevelAssessmentSubmitSerializer(data=request.data, context={'attempt': attempt})
        serializer.is_valid(raise_exception=True)

        answers_by_question_id = {
            answer_data['question'].id: [choice.id for choice in answer_data['selected_choices']]
            for answer_data in serializer.validated_data['answers']
        }
        finalize_level_assessment_attempt(attempt, answers_by_question_id=answers_by_question_id)

        return Response(LevelAssessmentAttemptSerializer(attempt, context={'request': request}).data)
