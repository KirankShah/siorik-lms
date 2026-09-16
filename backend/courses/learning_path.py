"""
Assembles a learner's "My Learning Path" dashboard section — the single
sequential trail of courses assigned to their role, with a
completed/current/locked state per course.

Design notes:

- Path membership: once an organization has configured Role-Based Training,
  courses come from LevelCourseAssignment for the learner's exact assessment
  level, in the Org Admin's configured order. Organizations with no assignments
  at all retain the legacy cumulative Course.path_order /
  Course.minimum_assessment_level behavior until they are configured.
- Sequential unlock: courses unlock strictly in path_order, purely on whether
  the immediately preceding path course is completed. Nothing about a
  Level Assessment gates a course's unlock state — passing one is a
  separate, standalone achievement (it gates the single Learning Path
  Completion Certificate — see certificates.services — and its own
  tier-complete/streak badges), never a course-access requirement. This is
  deliberate: levelassessments.services.assigned_assessment_level_for_user
  only ever lets a learner sit the ONE assessment matching their own exact
  assessment_level, never a lower tier's — so gating a lower-tier course's
  unlock on passing that lower tier's assessment would make it permanently
  unreachable for anyone whose own tier is higher.
- Milestone tint: once every course in a tier is completed, that tier is
  flagged is_complete so the frontend can shift it to the gold "completed
  milestone" tint instead of the ordinary per-course teal.
"""

from dataclasses import dataclass

from django.db.models import Count, Q

from accounts.models import User
from gamification.models import UserBadge
from gamification.services import award_badges_by_keys
from levelassessments.models import LevelAssessmentAttempt

from .models import Course, Enrollment, LevelCourseAssignment
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


# Ordinal seniority of each tier, matching accounts.User.AssessmentLevel's
# own declared order (ascending: assistant_supervisor, officer, management,
# senior_management).
TIER_RANK_ORDER = [choice.value for choice in User.AssessmentLevel]


def tier_rank(minimum_assessment_level):
    """
    Ordinal rank of a tier for "at or below" comparisons — None (Foundation)
    ranks below every real tier. Used both by _path_courses_for_user below
    (which tiers belong in a learner's own cumulative path) and by
    gamification.services.recalculate_leaderboard_entry (which of a
    learner's completed courses count toward their leaderboard score) —
    the same comparison, so the two stay consistent with each other.
    """
    if minimum_assessment_level is None:
        return -1
    return TIER_RANK_ORDER.index(minimum_assessment_level)


def has_passed_tier_assessment(user, tier_code):
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


@dataclass(frozen=True)
class PathCourseEntry:
    course: Course
    order: int
    tier_code: str | None


def _path_course_entries_for_user(user):
    """Ordered path entries for a learner.

    A single assignment anywhere in the organization activates the new exact-
    level configuration for that organization. This makes an intentionally
    empty level stay empty instead of silently falling back to legacy courses,
    while organizations not migrated to Role-Based Training continue to use
    their existing cumulative path unchanged.
    """
    organization_assignments = LevelCourseAssignment.objects.filter(
        assessment_level__organization_id=user.organization_id
    )
    if user.organization_id is not None and organization_assignments.exists():
        if not user.assessment_level:
            return []
        assignments = (
            organization_assignments
            .filter(
                assessment_level__name=user.assessment_level,
                course__in=visible_courses_for_user(user),
            )
            .select_related('course')
            .order_by('order', 'id')
        )
        return [
            PathCourseEntry(
                course=assignment.course,
                order=assignment.order,
                tier_code=user.assessment_level,
            )
            for assignment in assignments
        ]

    # Compatibility path for organizations that have not configured any
    # LevelCourseAssignment rows yet.
    user_tier_rank = tier_rank(user.assessment_level)
    allowed_tiers = [level for level in TIER_RANK_ORDER if tier_rank(level) <= user_tier_rank]

    tier_filter = Q(minimum_assessment_level__isnull=True)
    if allowed_tiers:
        tier_filter |= Q(minimum_assessment_level__in=allowed_tiers)

    courses = list(
        visible_courses_for_user(user)
        .filter(path_order__isnull=False)
        .filter(tier_filter)
        .order_by('path_order', 'id')
    )
    return [
        PathCourseEntry(
            course=course,
            order=course.path_order,
            tier_code=course.minimum_assessment_level,
        )
        for course in courses
    ]


def learning_path_course_ids(user):
    """Course ids in the learner's effective path, in configured order."""
    return [entry.course.id for entry in _path_course_entries_for_user(user)]


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
    entries = _path_course_entries_for_user(user)
    courses = [entry.course for entry in entries]
    course_ids = [course.id for course in courses]

    enrollment_by_course_id = {
        enrollment.course_id: enrollment
        for enrollment in Enrollment.objects.filter(user=user, course_id__in=course_ids)
    }

    course_states = {}
    previous_course_completed = True  # nothing blocks the very first path course
    current_node_assigned = False
    for course in courses:
        enrollment = enrollment_by_course_id.get(course.id)
        is_completed = bool(enrollment and enrollment.status == Enrollment.Status.COMPLETED)
        # Purely sequential — unlocking never depends on having passed any
        # Level Assessment (see this module's own docstring for why).
        is_unlocked = previous_course_completed

        if is_completed:
            state = 'completed'
        elif is_unlocked and not current_node_assigned:
            state = 'current'
            current_node_assigned = True
        else:
            state = 'locked'

        course_states[course.id] = state
        previous_course_completed = is_completed

    # In configured organizations this is one exact role tier. In legacy
    # organizations it retains the existing Foundation-to-current sequence.
    tier_order = list(dict.fromkeys(entry.tier_code for entry in entries))

    tiers = []
    for tier_code in tier_order:
        tier_entries = [entry for entry in entries if entry.tier_code == tier_code]
        if not tier_entries:
            continue
        tiers.append({
            'tier_key': _tier_key(tier_code),
            'tier_label': _tier_label(tier_code),
            'is_complete': all(course_states[entry.course.id] == 'completed' for entry in tier_entries),
            'courses': [
                {
                    'id': entry.course.id,
                    'slug': entry.course.slug,
                    'title': entry.course.title,
                    # Kept as path_order in the API contract; for configured
                    # role paths this is LevelCourseAssignment.order.
                    'path_order': entry.order,
                    'state': course_states[entry.course.id],
                }
                for entry in tier_entries
            ],
        })

    return {
        'branch_percentile': branch_completion_percentile(user, course_ids),
        'tiers': tiers,
    }


# One "<Tier> Complete" badge per tier a learner's path can include, keyed by
# the same tier_key build_learning_path produces (FOUNDATION_TIER_KEY or one
# of accounts.User.AssessmentLevel's codes). Seeded in
# gamification/migrations/0009_seed_tier_and_streak_badges.py.
TIER_COMPLETE_BADGE_KEYS = {
    FOUNDATION_TIER_KEY: 'tier_complete_foundation',
    User.AssessmentLevel.ASSISTANT_SUPERVISOR: 'tier_complete_assistant_supervisor',
    User.AssessmentLevel.OFFICER: 'tier_complete_officer',
    User.AssessmentLevel.MANAGEMENT: 'tier_complete_management',
    User.AssessmentLevel.SENIOR_MANAGEMENT: 'tier_complete_senior_management',
}


def check_learning_path_milestones(user):
    """
    Call this whenever a course belonging to `user`'s Learning Path has just
    become complete (see the `newly_completed` hook in
    courses.views.EnrollmentViewSet.slide_progress/complete_lesson).

    Re-derives the path fresh via build_learning_path — there's no persisted
    "is this tier complete" flag to diff against, see that function's own
    docstring — and:
    - awards this tier's "<Tier> Complete" badge for every tier that's now
      fully done. award_badges_by_keys is idempotent, so calling this after
      every completion (not just the one that actually finished a tier) is
      safe and simpler than tracking the transition separately.
    - reports back which tier(s) THIS call newly completed (i.e. the badge
      wasn't already earned a moment ago), for the frontend's one-time
      congratulatory mascot message, and whether the entire path is now
      done, for the certificate reveal moment.

    Returns {'newly_completed_tiers': [{'tier_key', 'tier_label', 'course_count'}, ...],
    'path_fully_completed': bool}.
    """
    already_earned_tier_badges = set(
        UserBadge.objects.filter(
            user=user, badge__key__in=TIER_COMPLETE_BADGE_KEYS.values()
        ).values_list('badge__key', flat=True)
    )

    path = build_learning_path(user)

    newly_completed_tiers = []
    badge_keys_to_award = []
    for tier in path['tiers']:
        if not tier['is_complete']:
            continue
        badge_key = TIER_COMPLETE_BADGE_KEYS.get(tier['tier_key'])
        if badge_key is None:
            continue
        badge_keys_to_award.append(badge_key)
        if badge_key not in already_earned_tier_badges:
            newly_completed_tiers.append({
                'tier_key': tier['tier_key'],
                'tier_label': tier['tier_label'],
                'course_count': len(tier['courses']),
            })

    award_badges_by_keys(user, badge_keys_to_award)

    all_path_courses = [course for tier in path['tiers'] for course in tier['courses']]
    path_fully_completed = bool(all_path_courses) and all(
        course['state'] == 'completed' for course in all_path_courses
    )

    return {'newly_completed_tiers': newly_completed_tiers, 'path_fully_completed': path_fully_completed}
