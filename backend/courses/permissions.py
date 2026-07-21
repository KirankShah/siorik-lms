from django.db.models import Q

from .models import Course


def visible_courses_for_user(user):
    """
    Courses a given user is allowed to see:

    - PLATFORM_ADMIN: every course, published or not.
    - ORG_ADMIN: every course belonging to their organization (published or
      not), plus platform-wide (organization=None) courses.
    - Everyone else (LEARNER/INSTRUCTOR): published courses that are either
      platform-wide or belong to their own organization.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return Course.objects.all()

    org_or_platform = Q(organization__isnull=True) | Q(organization=user.organization_id)

    if user.role == user.Role.ORG_ADMIN:
        return Course.objects.filter(org_or_platform)

    return Course.objects.filter(org_or_platform, is_published=True)
