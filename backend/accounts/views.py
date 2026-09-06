import csv
import io

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from audit.models import AuditLog
from audit.services import log_action
from core.permissions import IsAdminRole, IsPlatformAdminRole

from .models import Organization, User
from .serializers import (
    DemoUserCreateSerializer,
    OrganizationSerializer,
    SetPasswordSerializer,
    UserPreferenceSerializer,
    UserSerializer,
)
from .services import UserProvisioningError, provision_demo_user, provision_org_admin


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


class MeView(RetrieveUpdateAPIView):
    """
    GET returns the full (read-only) profile. PATCH is narrower — only
    self-service preferences (currently just preferred_narration_language)
    go through UserPreferenceSerializer, so a learner can't use this endpoint
    to change their own role/organization/etc.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return UserPreferenceSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(UserSerializer(request.user).data)


class OrganizationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    List/retrieve is available to any admin role (used to assign course
    access, pick an org for demo-user provisioning, etc.) — creating or
    deleting an organization is a platform-level action (onboarding/
    off-boarding a client), so both are restricted to PLATFORM_ADMIN
    specifically; see get_permissions.
    """

    queryset = Organization.objects.filter(is_active=True).order_by('name')
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [IsAuthenticated(), IsPlatformAdminRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        organization = serializer.save()
        log_action(self.request.user, AuditLog.Action.ORGANIZATION_CREATED, organization)

    def perform_destroy(self, instance):
        # A hard delete would SET_NULL every attached User/Course's
        # organization FK rather than fail loudly — silently orphaning real
        # accounts and content. Only allow deleting an organization that has
        # none, so this is only ever a cleanup action for an empty/mistaken
        # entry, never an accidental off-boarding of a live client.
        if instance.users.exists() or instance.courses.exists():
            raise ValidationError({
                'detail': (
                    'This organization still has users or courses attached. '
                    'Reassign or remove them before deleting it.'
                )
            })
        log_action(self.request.user, AuditLog.Action.ORGANIZATION_DELETED, instance)
        instance.delete()


CSV_EXPECTED_HEADER = ['name', 'email', 'organization', 'designation', 'phone_number']
# Older 3-column files (pre-designation/phone_number) still work — only the
# first 3 columns are required, so a legacy header is recognized too.
CSV_LEGACY_HEADER = CSV_EXPECTED_HEADER[:3]

# The extended column set (corporate title, functional title, branch/department,
# assessment level) is matched by header name rather than position, since it's a
# superset of unrelated fields with no natural fixed order. A header row is
# required for this format — maps normalized header cell -> field name.
CSV_EXTENDED_HEADER_FIELDS = {
    'name': 'name',
    'email': 'email',
    'corporate title': 'corporate_title',
    'functional title': 'functional_title',
    'branch/department': 'branch_department',
    'assessment level': 'assessment_level',
    'organization': 'organization',
}


def _resolve_organization(name_or_slug):
    name_or_slug = name_or_slug.strip()
    return (
        Organization.objects.filter(name__iexact=name_or_slug).first()
        or Organization.objects.filter(slug__iexact=name_or_slug).first()
    )


def _resolve_assessment_level(raw):
    """Matches case/spacing-insensitively against the four allowed values
    (e.g. "Senior Management" or "senior_management" both resolve), returning
    None for anything else — including a blank cell — so the caller can reject
    the row rather than silently defaulting it."""
    normalized = (raw or '').strip().lower().replace(' ', '_').replace('/', '_')
    return normalized if normalized in User.AssessmentLevel.values else None


def _row_cell(row, index):
    return row[index].strip() if index < len(row) else ''


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
        except UserProvisioningError as exc:
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

        extended_columns = None  # field name -> column index, when the extended header is used
        if rows:
            header = [c.strip().lower() for c in rows[0]]
            if header[:5] == CSV_EXPECTED_HEADER or header[:3] == CSV_LEGACY_HEADER:
                rows = rows[1:]
            elif set(header) == set(CSV_EXTENDED_HEADER_FIELDS):
                extended_columns = {
                    field: header.index(column) for column, field in CSV_EXTENDED_HEADER_FIELDS.items()
                }
                rows = rows[1:]

        created = []
        failed = []
        seen_emails = set()

        for index, row in enumerate(rows, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue  # blank line

            corporate_title = functional_title = branch_department = ''
            assessment_level = None

            if extended_columns is not None:
                name = _row_cell(row, extended_columns['name'])
                email = _row_cell(row, extended_columns['email'])
                org_name = _row_cell(row, extended_columns['organization'])
                corporate_title = _row_cell(row, extended_columns['corporate_title'])
                functional_title = _row_cell(row, extended_columns['functional_title'])
                branch_department = _row_cell(row, extended_columns['branch_department'])
                designation = ''
                phone_number = ''

                assessment_level_raw = _row_cell(row, extended_columns['assessment_level'])
                assessment_level = _resolve_assessment_level(assessment_level_raw)
                if assessment_level is None:
                    failed.append({
                        'row': index,
                        'email': email,
                        'reason': (
                            f'Invalid Assessment Level "{assessment_level_raw}": must be one of '
                            + ', '.join(User.AssessmentLevel.values) + '.'
                        ),
                    })
                    continue
            else:
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
                    corporate_title=corporate_title,
                    functional_title=functional_title,
                    branch_department=branch_department,
                    assessment_level=assessment_level,
                )
            except UserProvisioningError as exc:
                failed.append({'row': index, 'email': email, 'reason': str(exc)})
                continue

            log_action(request.user, AuditLog.Action.DEMO_USER_CREATED, user)
            created.append(email)

        return Response({'created': created, 'failed': failed})


class OrgAdminViewSet(viewsets.GenericViewSet):
    """
    PLATFORM_ADMIN-only provisioning of ORG_ADMIN accounts for a given
    organization — the counterpart to DemoUserViewSet, but creates a real
    (non-demo) administrator account: is_demo=False, role=ORG_ADMIN, and a
    distinctly-worded invite email (not "demo access" — this is an ongoing
    administrator role for their own institution). Restricted to
    PLATFORM_ADMIN rather than the broader admin roles: designating who
    administers a client organization is a platform onboarding action, not
    something an org's own admin does for themselves.
    """

    permission_classes = [IsAuthenticated, IsPlatformAdminRole]
    serializer_class = DemoUserCreateSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = provision_org_admin(**serializer.validated_data)
        except UserProvisioningError as exc:
            raise ValidationError({'detail': str(exc)})

        log_action(request.user, AuditLog.Action.ORG_ADMIN_CREATED, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


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
