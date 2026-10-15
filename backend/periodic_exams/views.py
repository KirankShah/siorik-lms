from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Organization

from .models import PeriodicExamSettings
from .permissions import IsExactOrgAdmin, IsExactPlatformAdmin
from .serializers import (
    CycleSerializer,
    PeriodicExamSettingsSerializer,
    PlatformOrganizationSerializer,
    PlatformToggleSerializer,
    ReadinessSerializer,
)
from .services import (
    PeriodicExamPoolConflictError,
    ensure_current_cycle,
    get_or_create_settings,
    question_counts_for_organizations,
    readiness_for_organization,
    set_feature_enabled,
)


class PeriodicExamConflictMixin:
    def handle_exception(self, exc):
        if isinstance(exc, PeriodicExamPoolConflictError):
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return super().handle_exception(exc)


class SettingsView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactOrgAdmin]

    def _get_row(self, request):
        row = get_or_create_settings(request.user.organization)
        if not row.enabled:
            return None
        row._current_cycle = ensure_current_cycle(request.user.organization)
        row._question_counts = question_counts_for_organizations([request.user.organization_id])[
            request.user.organization_id
        ]
        row.refresh_from_db()
        return row

    def get(self, request):
        row = self._get_row(request)
        if row is None:
            return Response({'detail': 'Not found.'}, status=404)
        return Response(PeriodicExamSettingsSerializer(row).data)

    def patch(self, request):
        row = self._get_row(request)
        if row is None:
            return Response({'detail': 'Not found.'}, status=404)
        serializer = PeriodicExamSettingsSerializer(row, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        updated._current_cycle = ensure_current_cycle(request.user.organization)
        updated._question_counts = question_counts_for_organizations([request.user.organization_id])[
            request.user.organization_id
        ]
        updated.refresh_from_db()
        return Response(PeriodicExamSettingsSerializer(updated).data)


class PlatformOrganizationListView(APIView):
    permission_classes = [IsAuthenticated, IsExactPlatformAdmin]

    def get(self, request):
        organizations = list(Organization.objects.filter(is_active=True).order_by('name'))
        settings_by_org = {
            row.organization_id: row
            for row in PeriodicExamSettings.objects.filter(
                organization_id__in=[org.id for org in organizations]
            )
        }
        counts_by_org = question_counts_for_organizations(org.id for org in organizations)
        data = [
            {
                'id': org.id,
                'name': org.name,
                'slug': org.slug,
                'is_active': org.is_active,
                'periodic_exam_enabled': settings_by_org.get(org.id).enabled if org.id in settings_by_org else False,
                'periodic_exam_enabled_from': settings_by_org.get(org.id).enabled_from if org.id in settings_by_org else None,
                'periodic_exam_question_counts': counts_by_org[org.id],
            }
            for org in organizations
        ]
        return Response(PlatformOrganizationSerializer(data, many=True).data)


class PlatformOrganizationToggleView(APIView):
    permission_classes = [IsAuthenticated, IsExactPlatformAdmin]

    def patch(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id, is_active=True)
        serializer = PlatformToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = set_feature_enabled(organization, serializer.validated_data['enabled'], request.user)
        return Response({
            'organization_id': organization.id,
            'enabled': row.enabled,
            'enabled_from': row.enabled_from,
        })


class AvailabilityView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.organization_id or user.role not in (user.Role.LEARNER, user.Role.ORG_ADMIN):
            return Response({'enabled': False})
        try:
            row = PeriodicExamSettings.objects.get(organization=user.organization)
        except PeriodicExamSettings.DoesNotExist:
            return Response({'enabled': False})
        if not row.enabled:
            return Response({'enabled': False})
        cycle = ensure_current_cycle(user.organization, timezone.now())
        if user.role == user.Role.LEARNER:
            eligibility_start = cycle.starts_at if cycle else row.enabled_from
            if (
                not user.is_active
                or user.is_demo
                or not getattr(user, 'assessment_level', None)
                or not eligibility_start
                or user.date_joined >= eligibility_start
            ):
                return Response({'enabled': False})
        return Response({
            'enabled': True,
            'available_from': row.enabled_from,
            'current_cycle': CycleSerializer(cycle).data if cycle else None,
        })


class ReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == user.Role.ORG_ADMIN and user.organization_id:
            organization = user.organization
            row = PeriodicExamSettings.objects.filter(organization=organization).first()
            if row is None or not row.enabled:
                return Response({'detail': 'Not found.'}, status=404)
        elif user.role == user.Role.PLATFORM_ADMIN:
            organization_id = request.query_params.get('organization_id')
            if not organization_id:
                return Response({'organization_id': ['This query parameter is required.']}, status=400)
            organization = get_object_or_404(Organization, pk=organization_id, is_active=True)
        else:
            return Response({'detail': 'You do not have permission to perform this action.'}, status=403)
        return Response(ReadinessSerializer(readiness_for_organization(organization)).data)
