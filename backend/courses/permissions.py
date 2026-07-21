from django.db.models import Q

from .models import Course


def visible_courses_for_user(user):
    """
    Courses a given user is allowed to see:

    - PLATFORM_ADMIN: every course, published or not.
    - ORG_ADMIN/INSTRUCTOR: every course belonging to their organization
      (published or not — instructors need to see/manage their own drafts),
      plus platform-wide (organization=None) courses.
    - LEARNER: published courses that are either platform-wide or belong to
      their own organization.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return Course.objects.all()

    org_or_platform = Q(organization__isnull=True) | Q(organization=user.organization_id)

    if user.role in (user.Role.ORG_ADMIN, user.Role.INSTRUCTOR):
        return Course.objects.filter(org_or_platform)

    return Course.objects.filter(org_or_platform, is_published=True)


def editable_courses_for_user(user):
    """
    Courses a given user is allowed to create/edit content for:

    - PLATFORM_ADMIN: every course.
    - INSTRUCTOR/ORG_ADMIN: courses belonging to their own organization, plus
      platform-wide courses. Unlike `visible_courses_for_user`, unpublished
      (draft) courses are included — authors need to edit drafts.
    - LEARNER: none.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return Course.objects.all()

    if user.role in (user.Role.ORG_ADMIN, user.Role.INSTRUCTOR):
        org_or_platform = Q(organization__isnull=True) | Q(organization=user.organization_id)
        return Course.objects.filter(org_or_platform)

    return Course.objects.none()
