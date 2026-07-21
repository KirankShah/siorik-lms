from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.permissions import IsAdminRole

from .models import Organization
from .serializers import OrganizationSerializer, UserSerializer


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class OrganizationViewSet(ReadOnlyModelViewSet):
    """Read-only org list, used by PLATFORM_ADMIN to assign courses to a specific org."""

    queryset = Organization.objects.filter(is_active=True).order_by('name')
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
