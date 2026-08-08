import csv
import io

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from audit.models import AuditLog
from audit.services import log_action
from core.permissions import IsAdminRole

from .models import Organization
from .serializers import DemoUserCreateSerializer, OrganizationSerializer, SetPasswordSerializer, UserSerializer
from .services import DemoUserProvisioningError, provision_demo_user


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


CSV_EXPECTED_HEADER = ['name', 'email', 'organization', 'designation', 'phone_number']
# Older 3-column files (pre-designation/phone_number) still work — only the
# first 3 columns are required, so a legacy header is recognized too.
CSV_LEGACY_HEADER = CSV_EXPECTED_HEADER[:3]


def _resolve_organization(name_or_slug):
    name_or_slug = name_or_slug.strip()
    return (
        Organization.objects.filter(name__iexact=name_or_slug).first()
        or Organization.objects.filter(slug__iexact=name_or_slug).first()
    )


class DemoUserViewSet(viewsets.GenericViewSet):
    """
    Admin-only provisioning of demo accounts — single add or CSV bulk upload.
    Both paths funnel through accounts.services.provision_demo_user so the
    duplicate-email/validation/email-failure handling only lives in one place.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = DemoUserCreateSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = provision_demo_user(**serializer.validated_data)
        except DemoUserProvisioningError as exc:
            raise ValidationError({'detail': str(exc)})

        log_action(request.user, AuditLog.Action.DEMO_USER_CREATED, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'A CSV file is required (field name "file").'}, status=400)

        try:
            decoded = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'detail': 'Could not read the uploaded file as UTF-8 text.'}, status=400)

        rows = list(csv.reader(io.StringIO(decoded)))
        if rows:
            header = [c.strip().lower() for c in rows[0]]
            if header[:5] == CSV_EXPECTED_HEADER or header[:3] == CSV_LEGACY_HEADER:
                rows = rows[1:]

        created = []
        failed = []
        seen_emails = set()

        for index, row in enumerate(rows, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue  # blank line

            if len(row) < 3:
                failed.append({
                    'row': index,
                    'email': row[1].strip() if len(row) >= 2 else '',
                    'reason': 'Malformed row: expected at least 3 columns (name, email, organization).',
                })
                continue

            name, email, org_name = (cell.strip() for cell in row[:3])
            designation = row[3].strip() if len(row) >= 4 else ''
            phone_number = row[4].strip() if len(row) >= 5 else ''
            email_key = email.lower()

            if not name or not email or not org_name:
                failed.append({'row': index, 'email': email, 'reason': 'Missing name, email, or organization.'})
                continue
            if email_key in seen_emails:
                failed.append({'row': index, 'email': email, 'reason': 'Duplicate email within this file.'})
                continue
            seen_emails.add(email_key)

            organization = _resolve_organization(org_name)
            if organization is None:
                failed.append({'row': index, 'email': email, 'reason': f'Organization "{org_name}" was not found.'})
                continue

            try:
                user = provision_demo_user(
                    name=name,
                    email=email,
                    organization=organization,
                    designation=designation,
                    phone_number=phone_number,
                )
            except DemoUserProvisioningError as exc:
                failed.append({'row': index, 'email': email, 'reason': str(exc)})
                continue

            log_action(request.user, AuditLog.Action.DEMO_USER_CREATED, user)
            created.append(email)

        return Response({'created': created, 'failed': failed})


class SetPasswordView(APIView):
    """
    Backs the forced-reset dialog (must_reset_password=True after demo-user
    provisioning) — its only caller. No current-password check: reaching this
    endpoint already requires a valid access token, which the user could only
    have obtained by authenticating with their current password moments
    earlier, so re-verifying it here would be redundant.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.must_reset_password = False
        user.save(update_fields=['password', 'must_reset_password'])

        log_action(user, AuditLog.Action.PASSWORD_RESET_COMPLETED, user)
        return Response(UserSerializer(user).data)
