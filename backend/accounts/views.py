from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from audit.models import AuditLog
from audit.services import log_action
from core.permissions import IsAdminRole

from .models import Organization
from .serializers import OrganizationSerializer, UserSerializer


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Login is rate-limited and audit-logged on success — brute-force defense."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        log_action(serializer.user, AuditLog.Action.LOGIN, serializer.user)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class MeView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class OrganizationViewSet(ReadOnlyModelViewSet):
    """Read-only org list, used by PLATFORM_ADMIN to assign courses to a specific org."""

    queryset = Organization.objects.filter(is_active=True).order_by('name')
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
