import random

from django.db import IntegrityError, transaction

from accounts.models import User

from .models import AssessmentLevel, LevelAssessmentAttempt, LevelQuestion

# Every organization gets exactly these four assessment tiers, one row per
# accounts.User.AssessmentLevel value. pass_threshold / questions_per_attempt
# start at the model defaults and are then editable per level, per org, by an
# admin (see AssessmentLevelViewSet.partial_update).
DEFAULT_LEVEL_NAMES = [choice.value for choice in User.AssessmentLevel]


def ensure_assessment_levels_for_organization(organization):
    """Idempotently create the four AssessmentLevel rows for `organization`.
    Safe to call repeatedly — used both by the post_save signal on
    Organization and the one-off backfill migration."""
    for name in DEFAULT_LEVEL_NAMES:
        AssessmentLevel.objects.get_or_create(organization=organization, name=name)


class LevelAssessmentError(Exception):
    """Raised for any attempt-start failure (already in progress, or too few
    questions in the pool to draw from) — callers report `str(exc)` back to
    the caller rather than letting it propagate as a 500."""


def assigned_assessment_level_for_user(user):
    """
    The single AssessmentLevel a user is assigned to sit, derived from their
    own organization + accounts.User.assessment_level. None if either isn't
    set on the user, or their organization hasn't configured a level for it.
    """
    if user.organization_id is None or not user.assessment_level:
        return None
    return AssessmentLevel.objects.filter(organization_id=user.organization_id, name=user.assessment_level).first()


def start_level_assessment_attempt(*, user, assessment_level):
    """
    Starts a new LevelAssessmentAttempt for `user` under `assessment_level`.

    Draws a fresh random sample of `assessment_level.questions_per_attempt`
    LevelQuestion ids from the full pool across ALL of that level's
    QuestionSets combined — QuestionSet is an authoring label only, so Set
    boundaries never affect the draw — and stores the drawn ids on the
    attempt itself so a graded attempt's exact question set stays auditable
    later even if the underlying pool changes.

    Only one attempt may be in progress (submitted_at is null) per
    user+assessment_level at a time; raises LevelAssessmentError if one
    already is. A prior completed/failed attempt never blocks a retake —
    each retake draws its own fresh random sample.
    """
    if LevelAssessmentAttempt.objects.filter(
        user=user, assessment_level=assessment_level, submitted_at__isnull=True
    ).exists():
        raise LevelAssessmentError('An attempt for this assessment level is already in progress.')

    pool = list(
        LevelQuestion.objects.filter(question_set__assessment_level=assessment_level).values_list('id', flat=True)
    )
    questions_per_attempt = assessment_level.questions_per_attempt
    if len(pool) < questions_per_attempt:
        raise LevelAssessmentError(
            f'Not enough questions in the pool ({len(pool)}) to draw {questions_per_attempt} for an attempt.'
        )

    questions_drawn = random.sample(pool, questions_per_attempt)

    try:
        with transaction.atomic():
            return LevelAssessmentAttempt.objects.create(
                user=user,
                assessment_level=assessment_level,
                questions_drawn=questions_drawn,
            )
    except IntegrityError as exc:
        # Backstop for the one_open_level_assessment_attempt_per_user_level
        # constraint under a race between the exists() check above and this
        # insert — the friendly message is the same either way.
        raise LevelAssessmentError('An attempt for this assessment level is already in progress.') from exc
