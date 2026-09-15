import random
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User

from .models import AssessmentLevel, LevelAssessmentAttempt, LevelChoice, LevelQuestion

# Every organization gets exactly these four assessment tiers, one row per
# accounts.User.AssessmentLevel value. Pass mark / questions-per-attempt are
# org-wide (org_settings.OrganizationSettings), not per level — see
# start_level_assessment_attempt below.
DEFAULT_LEVEL_NAMES = [choice.value for choice in User.AssessmentLevel]


def ensure_assessment_levels_for_organization(organization):
    """Idempotently create the four AssessmentLevel rows for `organization`.
    Safe to call repeatedly — used both by the post_save signal on
    Organization and the one-off backfill migration."""
    for name in DEFAULT_LEVEL_NAMES:
        AssessmentLevel.objects.get_or_create(organization=organization, name=name)


class LevelAssessmentError(Exception):
    """Raised for any attempt-start failure (already in progress, too few
    questions in the pool to draw from, or the organization's configured
    attempt cap has been reached) — callers report `str(exc)` back to the
    caller rather than letting it propagate as a 500."""


def assigned_assessment_level_for_user(user):
    """
    The single AssessmentLevel a user is assigned to sit, derived from their
    own organization + accounts.User.assessment_level. None if either isn't
    set on the user, or their organization hasn't configured a level for it.
    """
    if user.organization_id is None or not user.assessment_level:
        return None
    return AssessmentLevel.objects.filter(organization_id=user.organization_id, name=user.assessment_level).first()


def submitted_attempt_count(user, assessment_level):
    """How many of `user`'s attempts at `assessment_level` have ever been
    submitted (graded) — the count max_level_assessment_attempts caps.
    Deliberately counts every submitted attempt (the first plus every
    retake), not just failed ones: once the cap is reached there is no more
    retaking regardless of any individual attempt's own pass/fail."""
    return LevelAssessmentAttempt.objects.filter(
        user=user, assessment_level=assessment_level, submitted_at__isnull=False
    ).count()


def level_assessment_attempts_remaining(user, assessment_level):
    """None if unlimited (max_level_assessment_attempts is unset); otherwise
    how many more attempts `user` may still start at `assessment_level`, floored
    at 0. Used by MyAssessmentLevelView so the frontend can disable/explain the
    retake action before the learner even tries, not just after a 400."""
    max_attempts = assessment_level.organization.settings.max_level_assessment_attempts
    if max_attempts is None:
        return None
    return max(0, max_attempts - submitted_attempt_count(user, assessment_level))


def start_level_assessment_attempt(*, user, assessment_level):
    """
    Starts a new LevelAssessmentAttempt for `user` under `assessment_level`.

    Draws a fresh random sample of `assessment_level.organization.settings.
    questions_per_attempt` LevelQuestion ids from the full pool across ALL of that level's
    QuestionSets combined — QuestionSet is an authoring label only, so Set
    boundaries never affect the draw — and stores the drawn ids on the
    attempt itself so a graded attempt's exact question set stays auditable
    later even if the underlying pool changes.

    Only one attempt may be in progress (submitted_at is null) per
    user+assessment_level at a time; raises LevelAssessmentError if one
    already is. A prior completed/failed attempt never blocks a retake by
    itself — each retake draws its own fresh random sample — but
    OrganizationSettings.max_level_assessment_attempts (null = unlimited) is
    a hard cap on the total number of attempts (first + every retake); once
    reached, starting another is refused with a clear reason instead of
    silently allowing it.
    """
    if LevelAssessmentAttempt.objects.filter(
        user=user, assessment_level=assessment_level, submitted_at__isnull=True
    ).exists():
        raise LevelAssessmentError('An attempt for this assessment level is already in progress.')

    max_attempts = assessment_level.organization.settings.max_level_assessment_attempts
    if max_attempts is not None and submitted_attempt_count(user, assessment_level) >= max_attempts:
        raise LevelAssessmentError(
            f'You have reached the maximum of {max_attempts} attempt{"s" if max_attempts != 1 else ""} for this '
            'assessment level.'
        )

    pool = list(
        LevelQuestion.objects.filter(question_set__assessment_level=assessment_level).values_list('id', flat=True)
    )
    questions_per_attempt = assessment_level.organization.settings.questions_per_attempt
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


def _timing_settings(attempt):
    return attempt.assessment_level.organization.settings


def remaining_seconds_for_attempt(attempt, *, at=None):
    """
    Seconds left in the attempt's CURRENT timer segment — the current
    question's own countdown under PER_QUESTION timing, or the whole exam's
    under FIXED_TOTAL — computed fresh from timer_segment_started_at rather
    than stored, so it's correct whether this is a freshly-started attempt,
    a live one, or one just resumed after time away. Floored at 0; never
    negative. `at` is the current time to evaluate against (defaults to
    now()) — overridable so callers that resolve a catch-up and a
    remaining-time read against the exact same instant can do so.
    """
    settings_obj = _timing_settings(attempt)
    at = at or timezone.now()
    elapsed = (at - attempt.timer_segment_started_at).total_seconds()

    if settings_obj.timing_mode == settings_obj.TimingMode.FIXED_TOTAL:
        allocation = settings_obj.total_exam_minutes * 60
    else:
        allocation = settings_obj.seconds_per_question

    return max(0, round(allocation - elapsed))


def save_level_assessment_answer_progress(attempt, *, question, selected_choice_ids):
    """
    Persists the learner's current selection for `question` into
    answers_so_far — a scratch-pad for resume purposes only (see that
    field's own docstring on the model). Called on every answer change
    during a live attempt so a crash mid-selection still resumes correctly,
    not just a crash between questions.
    """
    answers_so_far = dict(attempt.answers_so_far or {})
    answers_so_far[str(question.id)] = list(selected_choice_ids)
    attempt.answers_so_far = answers_so_far
    attempt.save(update_fields=['answers_so_far'])
    return attempt


def advance_level_assessment_attempt(attempt, *, new_index):
    """
    Moves `attempt` to `new_index` — must be exactly one past the current
    index (the sequential flow never skips ahead or goes back; the resume
    catch-up path in resume_level_assessment_attempt is the only other thing
    that ever changes current_question_index, and it does so directly, not
    through this function). Under PER_QUESTION timing this also resets
    timer_segment_started_at to now — a fresh full countdown for the new
    question; under FIXED_TOTAL it's left untouched, since that segment is
    the whole attempt, not any one question.
    """
    if new_index != attempt.current_question_index + 1:
        raise LevelAssessmentError('Cannot advance out of sequence.')
    if new_index >= len(attempt.questions_drawn):
        raise LevelAssessmentError('No further questions in this attempt.')

    attempt.current_question_index = new_index
    update_fields = ['current_question_index']
    if _timing_settings(attempt).timing_mode == _timing_settings(attempt).TimingMode.PER_QUESTION:
        attempt.timer_segment_started_at = timezone.now()
        update_fields.append('timer_segment_started_at')
    attempt.save(update_fields=update_fields)
    return attempt


def finalize_level_assessment_attempt(attempt, *, answers_by_question_id):
    """
    Grades `attempt` from `answers_by_question_id` ({question_id: [choice_id,
    ...]}) and runs the exact same side effects a live, learner-initiated
    submit does (gamification points, badges, the Learning Path Completion
    Certificate check) — shared by levelassessments.views.
    LevelAssessmentAttemptViewSet.submit and the timeout auto-submit path in
    resume_level_assessment_attempt, so those two can never drift apart.
    Any question in questions_drawn missing from answers_by_question_id is
    graded as an empty (unanswered) selection — zero marks, same as a live
    per-question or whole-exam timeout.
    """
    # Deferred imports: avoids a circular import (certificates/gamification
    # import from courses, which doesn't import levelassessments, but the
    # long way round through their own submodules isn't worth risking at
    # module load time for a function that's only ever called at grading).
    from certificates.services import try_issue_learning_path_certificate
    from gamification.services import award_badges_for_level_assessment_attempt, update_gamification_for_user

    questions_by_id = LevelQuestion.objects.filter(id__in=attempt.questions_drawn).prefetch_related('choices').in_bulk()

    with transaction.atomic():
        for question_id in attempt.questions_drawn:
            question = questions_by_id.get(question_id)
            if question is None:
                continue  # deleted from the pool since the attempt was drawn
            selected_choice_ids = set(answers_by_question_id.get(question_id, []))
            correct_choice_ids = {choice.id for choice in question.choices.all() if choice.is_correct}
            is_correct = selected_choice_ids == correct_choice_ids

            answer, _created = attempt.answers.update_or_create(question=question, defaults={'is_correct': is_correct})
            answer.selected_choices.set(LevelChoice.objects.filter(id__in=selected_choice_ids))

        attempt.calculate_score_percent()
        update_gamification_for_user(attempt.user)
        award_badges_for_level_assessment_attempt(attempt)
        try_issue_learning_path_certificate(attempt.user)

    return attempt


def resume_level_assessment_attempt(attempt):
    """
    Call whenever an open (unsubmitted) attempt is fetched to resume it —
    e.g. after a browser crash, closed tab, or lost connection. Simulates
    however much real time has passed since timer_segment_started_at against
    the organization's configured allocation, applying exactly the same
    auto-advance (PER_QUESTION, possibly cascading through several questions
    whose time fully elapsed while the learner was away) or auto-submit
    (FIXED_TOTAL, or PER_QUESTION running out on the very last question) that
    would have triggered live, then persists the caught-up position. A no-op
    (besides the read) if the current segment hasn't actually expired, and
    always a no-op for an already-submitted attempt. Returns the attempt,
    possibly now submitted.
    """
    if attempt.submitted_at is not None:
        return attempt

    settings_obj = _timing_settings(attempt)
    now = timezone.now()

    if settings_obj.timing_mode == settings_obj.TimingMode.FIXED_TOTAL:
        if remaining_seconds_for_attempt(attempt, at=now) <= 0:
            return _auto_submit_expired_attempt(attempt)
        return attempt

    # PER_QUESTION: cascade forward through however many full per-question
    # segments have elapsed while away, each one scored as a timeout (whatever
    # was in answers_so_far for it, or nothing).
    seconds_per_question = settings_obj.seconds_per_question
    elapsed = (now - attempt.timer_segment_started_at).total_seconds()
    index = attempt.current_question_index
    last_index = len(attempt.questions_drawn) - 1

    while elapsed >= seconds_per_question and index < last_index:
        elapsed -= seconds_per_question
        index += 1

    if elapsed >= seconds_per_question:
        # Even the last question's time is used up — the whole attempt
        # auto-submits, same as if its live countdown had hit zero.
        return _auto_submit_expired_attempt(attempt)

    if index != attempt.current_question_index:
        attempt.current_question_index = index
        # Preserves the sub-second remainder of the current segment rather
        # than rounding it away, so remaining_seconds_for_attempt reads
        # exactly the same value a moment later whether or not this catch-up
        # had to run at all.
        attempt.timer_segment_started_at = now - timedelta(seconds=elapsed)
        attempt.save(update_fields=['current_question_index', 'timer_segment_started_at'])

    return attempt


def _auto_submit_expired_attempt(attempt):
    answers_by_question_id = {
        question_id: attempt.answers_so_far.get(str(question_id), []) for question_id in attempt.questions_drawn
    }
    return finalize_level_assessment_attempt(attempt, answers_by_question_id=answers_by_question_id)
