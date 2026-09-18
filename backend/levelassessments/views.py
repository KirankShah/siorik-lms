from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from audit.services import log_action
from core.permissions import IsAdminRole

from .imports import LevelQuestionImportError, import_level_questions, preview_replace_impact
from .models import LevelAssessmentAttempt, LevelQuestion
from .permissions import editable_assessment_levels_for_user
from .serializers import (
    AssessmentLevelSerializer,
    LevelAssessmentAdvanceSerializer,
    LevelAssessmentAnswerInputSerializer,
    LevelAssessmentAttemptSerializer,
    LevelAssessmentSubmitSerializer,
    LevelQuestionDetailSerializer,
    LevelQuestionEditSerializer,
    LevelQuestionListSerializer,
)
from .services import (
    LevelAssessmentError,
    advance_level_assessment_attempt,
    apply_question_edit,
    assigned_assessment_level_for_user,
    finalize_level_assessment_attempt,
    level_assessment_attempts_remaining,
    preview_level_assessment,
    resume_level_assessment_attempt,
    save_level_assessment_answer_progress,
    start_level_assessment_attempt,
    usage_count_for_question,
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

        `replace=true` scopes the import to a delete-then-recreate of only the
        Question Set labels present in the uploaded file (every other Question
        Set under this level is untouched) — see import_level_questions for
        why this is scoped rather than wiping the whole level. Because that
        delete cascades to any learner answer history on those questions, the
        frontend is expected to call this same endpoint with `dry_run=true`
        first (see preview_replace_impact) to show the admin exactly what a
        replace would remove before they confirm it.
        """
        assessment_level = self.get_object()

        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'An .xlsx file is required (field name "file").'}, status=400)

        replace = str(request.data.get('replace', '')).lower() in ('1', 'true')
        dry_run = str(request.data.get('dry_run', '')).lower() in ('1', 'true')

        try:
            if dry_run:
                return Response(preview_replace_impact(assessment_level=assessment_level, workbook_file=upload))

            created, failed = import_level_questions(
                assessment_level=assessment_level, workbook_file=upload, replace=replace,
            )
        except LevelQuestionImportError as exc:
            return Response({'detail': str(exc)}, status=400)

        if created:
            log_action(request.user, AuditLog.Action.LEVEL_QUESTIONS_IMPORTED, assessment_level)

        return Response({'created': created, 'failed': failed})

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """
        Admin-only content-review surface: simulates what one real attempt at
        this level would draw (same random sample as
        start_level_assessment_attempt), including the answer key — already
        safe to expose since this whole ViewSet is IsAdminRole-gated — but
        never creates a LevelAssessmentAttempt, so it can be called freely
        without affecting attempt counts, resume state, or reporting.
        """
        assessment_level = self.get_object()
        try:
            questions = preview_level_assessment(assessment_level)
        except LevelAssessmentError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response({
            'assessment_level': AssessmentLevelSerializer(assessment_level, context={'request': request}).data,
            'questions': LevelQuestionDetailSerializer(questions, many=True).data,
        })


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

        Runs the same away-time catch-up as `retrieve` before doing anything
        else — see the module-level note above `advance` for why this can't
        rely on the learner eventually triggering a GET.
        """
        attempt = self.get_object()
        attempt = resume_level_assessment_attempt(attempt)
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

        Runs the away-time catch-up first (same as `retrieve`) rather than
        trusting the client to ever have called GET: save_answer/advance/
        submit are the only endpoints a live in-progress session actually
        calls (see frontend/src/pages/LevelAssessmentPage.tsx), so without
        this, a learner who never triggers a reload could sit past their
        time allocation indefinitely and still have a late advance/submit
        accepted at face value. If the catch-up itself pushes the attempt
        into auto-submitted just now (this question's, or several cascaded
        questions', time fully elapsed during THIS request), that result is
        returned directly instead of a 400 — the frontend treats a submitted
        attempt in this response the same way it already treats one from
        `retrieve`. An attempt that was already submitted before this
        request even started (a genuine duplicate call) still gets the
        ordinary 400 below, unchanged.
        """
        attempt = self.get_object()
        was_already_submitted = attempt.submitted_at is not None
        attempt = resume_level_assessment_attempt(attempt)
        if attempt.submitted_at is not None and not was_already_submitted:
            return Response(LevelAssessmentAttemptSerializer(attempt, context={'request': request}).data)
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
        """
        Runs the same away-time catch-up as `retrieve`/`advance` first — see
        the docstring on `advance` for why. If the exam's time had already
        fully elapsed, the attempt is by this point already auto-submitted
        from whatever was saved via save-answer, and that graded result is
        returned as-is: a late submit doesn't get to inject answers the
        learner made after their time ran out. As with `advance`, this only
        applies when the catch-up is what submitted it just now — an attempt
        that was already submitted before this request started is still the
        ordinary 400 duplicate-submit error.
        """
        attempt = self.get_object()
        was_already_submitted = attempt.submitted_at is not None
        attempt = resume_level_assessment_attempt(attempt)
        if attempt.submitted_at is not None and not was_already_submitted:
            return Response(LevelAssessmentAttemptSerializer(attempt, context={'request': request}).data)
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


class LevelQuestionPagination(PageNumberPagination):
    """Server-side pagination for the Question Bank list — these pools grow
    with every import, never hand the browser the whole org's pool at once."""

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class LevelQuestionAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Question Bank admin surface: browse/filter/search the org's LevelQuestion
    pool (list), view a single question's complete record (retrieve), edit it
    (partial_update — reuses imports.py's own row-validation so an edit can
    never accept anything the Excel bulk import would reject), permanently
    delete one (destroy), and check how many past attempts used it before
    that delete (usage). Creation stays Excel-import-only (see
    AssessmentLevelViewSet.import_questions) — this surface never creates a
    question from scratch.

    Org scoping mirrors StaffEnrollmentViewSet: INSTRUCTOR/ORG_ADMIN are
    strictly confined to their own organization (the `organization` query
    param is never honored for them). PLATFORM_ADMIN gets every
    organization, filterable via ?organization=<id> same as
    StaffEnrollmentViewSet, combinable with ?assessment_level=<name> and
    ?search=<text>. The frontend is the one that defaults the Organization
    filter to unselected and holds off the initial fetch until PLATFORM_ADMIN
    picks something, rather than auto-loading every organization's entire
    pool on mount — a UX default, not a backend restriction, so a deliberate
    "every Officer-level question across every organization" filter (level
    alone, no organization) still works exactly as narrowly as it should.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]
    pagination_class = LevelQuestionPagination
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = LevelQuestion.objects.select_related(
            'question_set__assessment_level__organization'
        ).prefetch_related('choices').order_by(
            'question_set__assessment_level__organization_id',
            'question_set__assessment_level__name',
            'question_set__label', 'order', 'id',
        )

        user = self.request.user
        if user.role == user.Role.PLATFORM_ADMIN:
            organization_id = self.request.query_params.get('organization')
            if organization_id:
                queryset = queryset.filter(question_set__assessment_level__organization_id=organization_id)
        else:
            if user.organization_id is None:
                return queryset.none()
            queryset = queryset.filter(question_set__assessment_level__organization_id=user.organization_id)

        level_name = self.request.query_params.get('assessment_level')
        if level_name:
            queryset = queryset.filter(question_set__assessment_level__name=level_name)

        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(question_text__icontains=search)

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return LevelQuestionListSerializer
        return LevelQuestionDetailSerializer

    def partial_update(self, request, *args, **kwargs):
        question = self.get_object()
        serializer = LevelQuestionEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        apply_question_edit(question, serializer.validated_data)
        log_action(request.user, AuditLog.Action.LEVEL_QUESTION_UPDATED, question)

        question.refresh_from_db()
        return Response(LevelQuestionDetailSerializer(question, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        log_action(self.request.user, AuditLog.Action.LEVEL_QUESTION_DELETED, instance)
        instance.delete()

    @action(detail=True, methods=['get'])
    def usage(self, request, pk=None):
        """
        Read-only: how many LevelAssessmentAttempts drew this question,
        checked by the frontend before showing the delete confirmation so an
        admin deletes a previously-used question with full information —
        this never blocks the delete itself, only informs it.
        """
        question = self.get_object()
        return Response({'attempt_count': usage_count_for_question(question.id)})
