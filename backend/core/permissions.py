from rest_framework.permissions import BasePermission

ADMIN_ROLES = ('INSTRUCTOR', 'ORG_ADMIN', 'PLATFORM_ADMIN')
ORG_ADMIN_ROLES = ('ORG_ADMIN', 'PLATFORM_ADMIN')


class IsAdminRole(BasePermission):
    """Allows INSTRUCTOR, ORG_ADMIN, and PLATFORM_ADMIN — blocks LEARNER."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ADMIN_ROLES)


class IsOrgAdminRole(BasePermission):
    """Stricter than IsAdminRole — excludes INSTRUCTOR. ORG_ADMIN/PLATFORM_ADMIN only."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ORG_ADMIN_ROLES)


class RoleScopedQuerysetMixin:
    """
    Restricts a ViewSet's queryset by the requesting user's role:

    - PLATFORM_ADMIN: unrestricted (sees everything).
    - ORG_ADMIN: restricted to rows matching `org_lookup` against the user's
      organization (e.g. 'user__organization', 'course__organization').
    - Everyone else (LEARNER/INSTRUCTOR): restricted to rows matching
      `owner_lookup` against the user themself (e.g. 'user').

    Set `org_lookup`/`owner_lookup` as class attributes on the ViewSet.
    """

    org_lookup = None
    owner_lookup = None

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.role == user.Role.PLATFORM_ADMIN:
            return queryset

        if user.role == user.Role.ORG_ADMIN:
            if self.org_lookup is None or user.organization_id is None:
                return queryset.none()
            return queryset.filter(**{self.org_lookup: user.organization_id})

        if self.owner_lookup is None:
            return queryset.none()
        return queryset.filter(**{self.owner_lookup: user})
