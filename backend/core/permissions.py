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
