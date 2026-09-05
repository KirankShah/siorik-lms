from .models import AssessmentLevel


def editable_assessment_levels_for_user(user):
    """
    AssessmentLevel rows a given user is allowed to manage (list, import
    questions into) — mirrors courses.permissions.editable_courses_for_user's
    exact scoping shape:

    - PLATFORM_ADMIN: every AssessmentLevel, any organization.
    - ORG_ADMIN/INSTRUCTOR: only their own organization's AssessmentLevels.
    - LEARNER: none.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return AssessmentLevel.objects.all()

    if user.role in (user.Role.ORG_ADMIN, user.Role.INSTRUCTOR):
        return AssessmentLevel.objects.filter(organization_id=user.organization_id)

    return AssessmentLevel.objects.none()
