from decimal import Decimal

from django.db.models import Max

from assessments.models import QuizAttempt
from courses.models import Enrollment

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
    Not called on every dashboard read — only from the two events that can
    change it (course completion, quiz attempt); see
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
