from django.http import FileResponse, Http404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsOrgAdminRole

from .permissions import visible_resources_for_user
from .serializers import ResourceSerializer


class ResourceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Org-scoped PDF document library. List/retrieve/stream is read-only for
    any authenticated user — LEARNER/INSTRUCTOR/ORG_ADMIN see only their own
    organization's resources, PLATFORM_ADMIN sees every organization's (see
    visible_resources_for_user). Upload is ORG_ADMIN-only and always scoped
    to the caller's own organization server-side (never a client-supplied
    org id). ORG_ADMIN can delete any resource in their organization, while
    PLATFORM_ADMIN can delete any resource. All of this is enforced here,
    not just hidden in the authoring UI, so a direct API request from another
    organization — or from a LEARNER — is denied, not merely unreachable
    through the UI.
    """

    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [IsAuthenticated(), IsOrgAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return visible_resources_for_user(self.request.user).select_related('uploaded_by')

    def perform_create(self, serializer):
        user = self.request.user
        if user.organization_id is None:
            raise ValidationError({'detail': 'You must belong to an organization to upload a resource.'})
        serializer.save(organization=user.organization, uploaded_by=user)

    def perform_destroy(self, instance):
        # The destroy permission allows ORG_ADMIN and PLATFORM_ADMIN only,
        # and get_object() has already applied organization scoping.
        instance.delete()

    @action(detail=True, methods=['get'])
    def stream(self, request, pk=None):
        """
        GET /api/resources/<id>/stream/ — inline (not attachment) PDF bytes
        for the protected in-browser viewer. get_object() runs the same
        get_queryset() org scoping as list/retrieve, so a learner from
        another organization gets 404 here too, not the file.
        """
        resource = self.get_object()
        try:
            file_handle = resource.file.open('rb')
        except FileNotFoundError:
            raise Http404('Resource file is missing.')
        response = FileResponse(file_handle, content_type='application/pdf')
        response['Content-Disposition'] = 'inline'
        # Every viewer session re-checks this user's live org membership on
        # every stream request — nothing here should be cached by a
        # shared/proxy cache.
        response['Cache-Control'] = 'private, max-age=0, no-store'
        return response
