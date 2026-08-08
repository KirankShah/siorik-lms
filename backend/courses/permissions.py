from django.db.models import Case, IntegerField, Q, Value, When

from .models import Course, DemoLessonAccess


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


def catalog_courses_for_user(user):
    """
    The queryset a course-list/catalog view should enumerate. Identical to
    visible_courses_for_user for every ordinary user (including its default
    Course.Meta ordering, -created_at). For a demo user (LEARNER,
    is_demo=True) this deliberately widens to every published course
    platform-wide — including ones outside their own Organization's normal
    assignment — so the catalog can render those as locked teaser cards
    instead of hiding them outright. Accessible (unlocked) courses are
    sorted before locked ones — same -created_at order within each group —
    so a demo user's one or two real courses aren't buried below a wall of
    locked teasers; the accessible set is the exact same
    visible_courses_for_user(user) the serializer's is_locked flag checks
    against, so the sort and the flag can never disagree.

    This is catalog-listing only: retrieval of a single course, and every
    content-fetching endpoint below it (modules/lessons/elements/quizzes/
    etc.), all stay gated by visible_courses_for_user alone, so a locked
    course's detail/content is never actually reachable server-side even
    though its card is visible — force-navigating to its URL 404s.
    """
    if getattr(user, 'is_demo', False):
        accessible_ids = visible_courses_for_user(user).values_list('id', flat=True)
        return (
            Course.objects.filter(is_published=True)
            .annotate(
                _demo_locked=Case(
                    When(id__in=accessible_ids, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by('_demo_locked', '-created_at')
        )
    return visible_courses_for_user(user)


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


def is_lesson_locked_for_demo_user(user, lesson):
    """
    True only for a demo user (accounts.User.is_demo=True) opening a lesson
    that isn't explicitly granted via DemoLessonAccess within an
    is_demo_available course. Non-demo users, and any user on a course that
    isn't demo-restricted, are never locked out here — this function is
    purely additive on top of the normal visible_courses_for_user check,
    never a replacement for it.
    """
    if not getattr(user, 'is_demo', False):
        return False
    course = lesson.module.course
    if not course.is_demo_available:
        return False
    return not DemoLessonAccess.objects.filter(course=course, lesson=lesson).exists()


def exclude_demo_locked(queryset, user, lesson_path):
    """
    Further restricts an already visible_courses_for_user-scoped queryset of
    slide-owned rows (Element, Quiz, Assignment, ScenarioNode, ...), removing
    any row whose lesson is demo-locked for this user — see
    is_lesson_locked_for_demo_user. `lesson_path` is the queryset's ORM path
    to the owning Lesson, e.g. 'slide__lesson' for a model with a direct
    `slide` FK. No-op (returns the queryset unchanged) for non-demo users,
    which is the overwhelming majority of requests.
    """
    if not getattr(user, 'is_demo', False):
        return queryset

    restricted_course_ids = set(Course.objects.filter(is_demo_available=True).values_list('id', flat=True))
    if not restricted_course_ids:
        return queryset

    allowed_lesson_ids = set(
        DemoLessonAccess.objects.filter(course_id__in=restricted_course_ids).values_list('lesson_id', flat=True)
    )
    course_lookup = f'{lesson_path}__module__course_id__in'
    lesson_lookup = f'{lesson_path}_id__in'
    return queryset.exclude(
        Q(**{course_lookup: restricted_course_ids}) & ~Q(**{lesson_lookup: allowed_lesson_ids})
    )
