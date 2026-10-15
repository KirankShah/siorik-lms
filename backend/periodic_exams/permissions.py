from rest_framework.permissions import BasePermission


class IsExactOrgAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == request.user.Role.ORG_ADMIN
            and request.user.organization_id
        )


class IsExactPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == request.user.Role.PLATFORM_ADMIN
        )
