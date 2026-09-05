from decimal import Decimal

from django.db.models import Max

from assessments.models import QuizAttempt
from certificates.models import Certificate
from courses.models import Enrollment
from levelassessments.models import LevelAssessmentAttempt

from .models import Badge, LeaderboardEntry, UserBadge

COURSE_COMPLETION_POINTS = 100
MAX_QUIZ_BONUS_POINTS = 50

# Minimum distinct quizzes attempted before HIGH_ACHIEVER can be earned, so a
# single lucky attempt doesn't trigger it.
HIGH_ACHIEVER_MIN_QUIZZES = 3
HIGH_ACHIEVER_MIN_AVERAGE = Decimal('90')


def _best_scores_per_quiz(user, quiz_filter=None):
    """Each quiz's best score_percent this user has achieved, as a list."""
    queryset = QuizAttempt.objects.filter(user=user)
    if quiz_filter:
        queryset = queryset.filter(**quiz_filter)
    return list(queryset.values('quiz_id').annotate(best=Max('score_percent')).values_list('best', flat=True))


def _average(values):
    if not values:
        return Decimal('0')
    return sum(values) / len(values)


def recalculate_leaderboard_entry(user):
    """
    Recomputes and persists this user's LeaderboardEntry: 100 points per
    completed course, plus up to 50 bonus points scaled linearly to that
    course's own quiz average (each quiz counted once, at its best score).
    Not called on every dashboard read — only from the events that can change
    it (course completion, quiz attempt, certificate generation); see
    update_gamification_for_user.
    """
    if user.organization_id is None:
        return None

    completed_enrollments = Enrollment.objects.filter(user=user, status=Enrollment.Status.COMPLETED)

    total_points = 0
    for enrollment in completed_enrollments:
        course_scores = _best_scores_per_quiz(user, {'quiz__slide__lesson__module__course': enrollment.course_id})
        course_average = _average(course_scores)
        total_points += COURSE_COMPLETION_POINTS + round(MAX_QUIZ_BONUS_POINTS * (course_average / 100))

    overall_average = _average(_best_scores_per_quiz(user))

    entry, _created = LeaderboardEntry.objects.update_or_create(
        user=user,
        defaults={
            'organization_id': user.organization_id,
            'total_points': total_points,
            'courses_completed_count': completed_enrollments.count(),
            'average_quiz_score': overall_average,
            'certificates_earned_count': Certificate.objects.filter(user=user).count(),
        },
    )
    return entry


def award_badges_for_user(user):
    """Awards any badge whose condition is now met and wasn't already earned."""
    entry = LeaderboardEntry.objects.filter(user=user).first()
    if entry is None:
        return

    already_earned = set(UserBadge.objects.filter(user=user).values_list('badge__key', flat=True))
    to_award = []

    if entry.courses_completed_count >= 1 and 'first_course_complete' not in already_earned:
        to_award.append('first_course_complete')
    if entry.courses_completed_count >= 5 and 'five_courses_complete' not in already_earned:
        to_award.append('five_courses_complete')
    if 'perfect_score' not in already_earned and QuizAttempt.objects.filter(user=user, score_percent=100).exists():
        to_award.append('perfect_score')
    if 'high_achiever' not in already_earned:
        quiz_count = QuizAttempt.objects.filter(user=user).values('quiz_id').distinct().count()
        if quiz_count >= HIGH_ACHIEVER_MIN_QUIZZES and entry.average_quiz_score >= HIGH_ACHIEVER_MIN_AVERAGE:
            to_award.append('high_achiever')

    if not to_award:
        return

    badges_by_key = {badge.key: badge for badge in Badge.objects.filter(key__in=to_award)}
    for key in to_award:
        badge = badges_by_key.get(key)
        if badge:
            UserBadge.objects.get_or_create(user=user, badge=badge)


def update_gamification_for_user(user):
    """Single entry point called after a course completion or quiz attempt."""
    if recalculate_leaderboard_entry(user) is not None:
        award_badges_for_user(user)


def _attempt_has_three_correct_in_a_row(attempt):
    """
    True if `attempt` has three consecutive correct answers in *drawn* order
    — the sequence questions_drawn stores (see
    levelassessments.services.start_level_assessment_attempt), which is the
    order the learner actually saw and answered them in. LevelQuestion's own
    `order` spans the whole pool it was drawn from, not this one attempt, so
    it isn't the right sequence to check a streak against.
    """
    correctness_by_question = dict(attempt.answers.values_list('question_id', 'is_correct'))
    streak = 0
    for question_id in attempt.questions_drawn:
        if correctness_by_question.get(question_id):
            streak += 1
            if streak >= 3:
                return True
        else:
            streak = 0
    return False


def _is_comeback_pass(attempt):
    """True if `attempt` passed and this user previously failed a submitted
    attempt at this same assessment level."""
    if not attempt.passed:
        return False
    return (
        LevelAssessmentAttempt.objects.filter(
            user=attempt.user, assessment_level=attempt.assessment_level, submitted_at__isnull=False, passed=False,
        )
        .exclude(id=attempt.id)
        .exists()
    )


def _is_first_in_branch_to_pass(attempt):
    """
    True if `attempt` passed and no other user sharing this user's
    organization + branch_department has ever passed this same assessment
    level. Branch/org scoped (not global) since branch_department is free
    text an admin fills in per user — different organizations may reuse the
    same branch name coincidentally.
    """
    if not attempt.passed:
        return False
    user = attempt.user
    branch = (user.branch_department or '').strip()
    if not branch or user.organization_id is None:
        return False
    return not (
        LevelAssessmentAttempt.objects.filter(
            assessment_level=attempt.assessment_level,
            passed=True,
            user__organization_id=user.organization_id,
            user__branch_department__iexact=branch,
        )
        .exclude(user=user)
        .exists()
    )


def award_badges_for_level_assessment_attempt(attempt):
    """
    Awards any level-assessment-specific badge whose condition is now met by
    this just-submitted attempt — called once, right after
    LevelAssessmentAttempt.calculate_score_percent(). Deliberately
    independent of award_badges_for_user/LeaderboardEntry: a user can sit a
    level assessment without ever having enrolled in a course, so there may
    be no LeaderboardEntry to gate on the way award_badges_for_user does.

    'perfect_score' is shared with the course-quiz path in
    award_badges_for_user — same badge, same key, just a second way to earn
    it — everything else here is level-assessment-only.
    """
    user = attempt.user
    already_earned = set(UserBadge.objects.filter(user=user).values_list('badge__key', flat=True))
    to_award = []

    if 'first_strike' not in already_earned:
        is_first_attempt = not LevelAssessmentAttempt.objects.filter(user=user).exclude(id=attempt.id).exists()
        if is_first_attempt and attempt.answers.filter(is_correct=True).exists():
            to_award.append('first_strike')

    if 'hat_trick' not in already_earned and _attempt_has_three_correct_in_a_row(attempt):
        to_award.append('hat_trick')

    if 'perfect_score' not in already_earned and attempt.score_percent == 100:
        to_award.append('perfect_score')

    if 'comeback' not in already_earned and _is_comeback_pass(attempt):
        to_award.append('comeback')

    if 'branch_pride' not in already_earned and _is_first_in_branch_to_pass(attempt):
        to_award.append('branch_pride')

    if not to_award:
        return

    badges_by_key = {badge.key: badge for badge in Badge.objects.filter(key__in=to_award)}
    for key in to_award:
        badge = badges_by_key.get(key)
        if badge:
            UserBadge.objects.get_or_create(user=user, badge=badge)
