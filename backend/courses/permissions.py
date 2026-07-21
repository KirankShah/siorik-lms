from django.db.models import Q

from .models import Course


def _org_scoped_courses(user):
    """
    Courses belonging to a user's own organization: their org's own
    ORGANIZATION-owned content, plus PLATFORM-owned courses explicitly
    granted to their org via CourseAccess. The organization FK on a
    PLATFORM-owned course does not itself grant access — only a CourseAccess
    row does.
    """
    if user.organization_id is None:
        return Course.objects.none()

    own_org_courses = Q(content_owner=Course.ContentOwner.ORGANIZATION, organization_id=user.organization_id)
    granted_platform_courses = Q(
        content_owner=Course.ContentOwner.PLATFORM,
        access_grants__organization_id=user.organization_id,
    )
    return Course.objects.filter(own_org_courses | granted_platform_courses).distinct()


def visible_courses_for_user(user):
    """
    Courses a given user is allowed to see:

    - PLATFORM_ADMIN: every course, published or not.
    - ORG_ADMIN/INSTRUCTOR: their org's own ORGANIZATION-owned courses
      (published or not — instructors need to see/manage their own drafts),
      plus PLATFORM-owned courses granted to their org.
    - LEARNER: the same set, restricted to published courses.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return Course.objects.all()

    if user.role in (user.Role.ORG_ADMIN, user.Role.INSTRUCTOR):
        return _org_scoped_courses(user)

    return _org_scoped_courses(user).filter(is_published=True)


def editable_courses_for_user(user):
    """
    Courses a given user is allowed to create/edit content for:

    - PLATFORM_ADMIN: every course.
    - INSTRUCTOR/ORG_ADMIN: only their own organization's ORGANIZATION-owned
      courses. Having been granted access to a PLATFORM-owned course lets
      their org's members view/enroll in it, but not edit its content —
      platform content stays platform-managed.
    - LEARNER: none.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return Course.objects.all()

    if user.role in (user.Role.ORG_ADMIN, user.Role.INSTRUCTOR):
        return Course.objects.filter(content_owner=Course.ContentOwner.ORGANIZATION, organization_id=user.organization_id)

    return Course.objects.none()
