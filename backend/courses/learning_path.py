"""
Assembles a learner's "My Learning Path" dashboard section — the single
sequential trail of path_order'd courses, grouped by tier, with a
completed/current/locked state per course.

Design notes (see the "Tier unlock rule" / "Path scope" decisions this
feature was built against):

- Path membership: every course visible to the learner (visible_courses_for_user)
  that has a path_order set, whether or not they're enrolled yet — enrolling
  happens implicitly the moment they open a path course via its Continue
  button, same as any other course.
- Tier membership: Course.minimum_assessment_level is null for "Foundation"
  (open to everyone), or one of accounts.User.AssessmentLevel's codes for a
  role tier. A learner never sees more than one non-Foundation tier in their
  own path — levelassessments.services.assigned_assessment_level_for_user is
  likewise scoped to exactly the single tier matching the learner's own
  User.assessment_level, never a ladder of lower ones, so there's no existing
  mechanism for a learner to sit any tier but their own.
- Sequential unlock: courses unlock strictly in path_order. A course is
  reachable only once the immediately preceding path course is completed
  AND (when it starts a new tier) the learner has PASSED that tier's
  LevelAssessmentAttempt — mirroring the existing "pass the level assessment"
  flow (levelassessments views/services) rather than inventing a new
  progression mechanism.
- Milestone tint: once every course in a tier is completed, that tier is
  flagged is_complete so the frontend can shift it to the gold "completed
  milestone" tint instead of the ordinary per-course teal.
"""

from django.db.models import Count, Q

from accounts.models import User
from levelassessments.models import LevelAssessmentAttempt

from .models import Course, Enrollment
from .permissions import visible_courses_for_user

FOUNDATION_TIER_KEY = 'FOUNDATION'
FOUNDATION_TIER_LABEL = 'Foundation'

_ASSESSMENT_LEVEL_LABELS = dict(User.AssessmentLevel.choices)


def _tier_key(minimum_assessment_level):
    return minimum_assessment_level or FOUNDATION_TIER_KEY


def _tier_label(minimum_assessment_level):
    if not minimum_assessment_level:
        return FOUNDATION_TIER_LABEL
    return _ASSESSMENT_LEVEL_LABELS.get(minimum_assessment_level, minimum_assessment_level)


def _has_passed_tier_assessment(user, tier_code):
    """Whether `user` has ever passed the LevelAssessmentAttempt for the
    AssessmentLevel named `tier_code` within their own organization — the
    same (user, org, name) lookup MyAssessmentLevelView/start() use via
    assigned_assessment_level_for_user."""
    if user.organization_id is None:
        return False
    return LevelAssessmentAttempt.objects.filter(
        user=user,
        assessment_level__organization_id=user.organization_id,
        assessment_level__name=tier_code,
        passed=True,
    ).exists()


def _path_courses_for_user(user):
    """Path-order'd courses visible to `user`, restricted to Foundation plus
    (if assigned) the single tier matching their own assessment_level."""
    tier_filter = Q(minimum_assessment_level__isnull=True)
    if user.assessment_level:
        tier_filter |= Q(minimum_assessment_level=user.assessment_level)

    return list(
        visible_courses_for_user(user)
        .filter(path_order__isnull=False)
        .filter(tier_filter)
        .order_by('path_order', 'id')
    )


def branch_completion_percentile(user, path_course_ids):
    """
    Of the learner's colleagues in the same organization + branch_department,
    what percentage have completed fewer of these path courses than the
    learner has. None whenever there's nothing meaningful to compare against
    (no branch set, no org, or no colleagues sharing that branch) — the
    frontend should just omit the line in that case rather than show a
    placeholder.
    """
    branch = (user.branch_department or '').strip()
    if not branch or user.organization_id is None or not path_course_ids:
        return None

    my_completed_count = Enrollment.objects.filter(
        user=user, course_id__in=path_course_ids, status=Enrollment.Status.COMPLETED
    ).count()

    colleagues = User.objects.filter(
        organization_id=user.organization_id,
        branch_department__iexact=branch,
    ).exclude(pk=user.pk)
    total_colleagues = colleagues.count()
    if total_colleagues == 0:
        return None

    fewer_completions = (
        colleagues.annotate(
            path_completed_count=Count(
                'enrollments',
                filter=Q(
                    enrollments__course_id__in=path_course_ids,
                    enrollments__status=Enrollment.Status.COMPLETED,
                ),
            )
        )
        .filter(path_completed_count__lt=my_completed_count)
        .count()
    )
    return round(fewer_completions / total_colleagues * 100)


def build_learning_path(user):
    """Returns {'branch_percentile': int|None, 'tiers': [...]} for `user`'s
    My Learning Path dashboard section. Each tier is
    {'tier_key', 'tier_label', 'is_complete', 'courses': [...]}; each course
    is {'id', 'slug', 'title', 'path_order', 'state'} where state is one of
    'completed' | 'current' | 'locked'."""
    courses = _path_courses_for_user(user)
    course_ids = [course.id for course in courses]

    enrollment_by_course_id = {
        enrollment.course_id: enrollment
        for enrollment in Enrollment.objects.filter(user=user, course_id__in=course_ids)
    }

    tier_gate_satisfied_cache = {}

    def tier_gate_satisfied(tier_code):
        if tier_code is None:
            return True
        if tier_code not in tier_gate_satisfied_cache:
            tier_gate_satisfied_cache[tier_code] = _has_passed_tier_assessment(user, tier_code)
        return tier_gate_satisfied_cache[tier_code]

    course_states = {}
    previous_course_completed = True  # nothing blocks the very first path course
    current_node_assigned = False
    for course in courses:
        enrollment = enrollment_by_course_id.get(course.id)
        is_completed = bool(enrollment and enrollment.status == Enrollment.Status.COMPLETED)
        is_unlocked = previous_course_completed and tier_gate_satisfied(course.minimum_assessment_level)

        if is_completed:
            state = 'completed'
        elif is_unlocked and not current_node_assigned:
            state = 'current'
            current_node_assigned = True
        else:
            state = 'locked'

        course_states[course.id] = state
        previous_course_completed = is_completed

    tier_order = [None]
    if user.assessment_level:
        tier_order.append(user.assessment_level)

    tiers = []
    for tier_code in tier_order:
        tier_courses = [course for course in courses if course.minimum_assessment_level == tier_code]
        if not tier_courses:
            continue
        tiers.append({
            'tier_key': _tier_key(tier_code),
            'tier_label': _tier_label(tier_code),
            'is_complete': all(course_states[course.id] == 'completed' for course in tier_courses),
            'courses': [
                {
                    'id': course.id,
                    'slug': course.slug,
                    'title': course.title,
                    'path_order': course.path_order,
                    'state': course_states[course.id],
                }
                for course in tier_courses
            ],
        })

    return {
        'branch_percentile': branch_completion_percentile(user, course_ids),
        'tiers': tiers,
    }
