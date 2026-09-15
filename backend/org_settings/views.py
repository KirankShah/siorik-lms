from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsOrgAdminRole

from .models import OrganizationSettings
from .serializers import OrganizationSettingsSerializer


class OrganizationSettingsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    One row per organization, auto-created (see signals.py) — there is no
    create action, only list/retrieve/update. ORG_ADMIN/PLATFORM_ADMIN only,
    enforced here server-side (not just hidden in the Settings UI): a
    LEARNER/INSTRUCTOR request is rejected regardless of what the frontend
    shows. ORG_ADMIN's queryset is scoped to their own organization's single
    row (no selector needed); PLATFORM_ADMIN sees every organization's, and
    the frontend offers an organization selector — reusing the same
    "list everything, let the client pick a slot" shape as
    certificates.views.CertificateTemplateViewSet.
    """

    serializer_class = OrganizationSettingsSerializer
    permission_classes = [IsAuthenticated, IsOrgAdminRole]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        queryset = OrganizationSettings.objects.select_related('organization')
        if user.role == user.Role.PLATFORM_ADMIN:
            return queryset
        if user.organization_id is None:
            return queryset.none()
        return queryset.filter(organization_id=user.organization_id)
