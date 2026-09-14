from .models import Resource


def visible_resources_for_user(user):
    """
    Resources a given user is allowed to read:

    - PLATFORM_ADMIN: every organization's resources.
    - Everyone else (LEARNER/INSTRUCTOR/ORG_ADMIN): only their own
      organization's — none if they don't belong to one.
    """
    if user.role == user.Role.PLATFORM_ADMIN:
        return Resource.objects.all()
    if user.organization_id is None:
        return Resource.objects.none()
    return Resource.objects.filter(organization_id=user.organization_id)
