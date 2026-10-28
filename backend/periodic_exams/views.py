from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Organization

from .models import PeriodicExamCycle, PeriodicExamSettings
from .permissions import IsExactLearner, IsExactOrgAdmin, IsExactPlatformAdmin
from .serializers import (
    AdvanceInputSerializer,
    CurrentAnswerInputSerializer,
    CycleSerializer,
    PeriodicExamSettingsSerializer,
    PlatformOrganizationSerializer,
    PlatformToggleSerializer,
    ReadinessSerializer,
)
from .services import (
    PeriodicExamError,
    PeriodicExamPoolConflictError,
    ensure_current_cycle,
    get_or_create_settings,
    question_counts_for_organizations,
    readiness_for_organization,
    advance_periodic_attempt,
    close_expired_periodic_attempts,
    revoke_ineligible_participants,
    get_periodic_attempt,
    periodic_attempt_payload,
    periodic_exam_history,
    periodic_exam_summary,
    save_periodic_answer,
    set_feature_enabled,
    start_periodic_exam_attempt,
    submit_periodic_attempt,
    upcoming_cycle_preview,
)
from .reports import (
    csv_report_response,
    iter_report_rows,
    report_participants,
    report_participants_for_organization,
    xlsx_report_response,
)


class PeriodicExamConflictMixin:
    def handle_exception(self, exc):
        if isinstance(exc, PeriodicExamError):
            return Response(
                {'detail': exc.detail, 'code': exc.code}, status=exc.status_code
            )
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


class PlatformOrganizationToggleView(PeriodicExamConflictMixin, APIView):
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
            'upcoming_cycle': None if cycle else upcoming_cycle_preview(row, timezone.now()),
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


class LearnerSummaryView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def get(self, request):
        cycle_id = request.query_params.get('cycle_id')
        try:
            cycle_id = int(cycle_id) if cycle_id else None
        except (TypeError, ValueError):
            raise PeriodicExamError('Invalid cycle_id.', code='INVALID_CYCLE')
        return Response(periodic_exam_summary(request.user, cycle_id=cycle_id))


class LearnerHistoryView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def get(self, request):
        return Response(periodic_exam_history(request.user))


class LearnerAttemptStartView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def post(self, request):
        cycle_id = request.query_params.get('cycle_id')
        try:
            cycle_id = int(cycle_id) if cycle_id else None
        except (TypeError, ValueError):
            raise PeriodicExamError('Invalid cycle_id.', code='INVALID_CYCLE')
        attempt, created = start_periodic_exam_attempt(request.user, cycle_id=cycle_id)
        return Response(
            periodic_attempt_payload(attempt),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LearnerAttemptView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def get(self, request, attempt_id):
        attempt = get_periodic_attempt(request.user, attempt_id)
        return Response(periodic_attempt_payload(attempt))


class LearnerCurrentAnswerView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def put(self, request, attempt_id):
        serializer = CurrentAnswerInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = save_periodic_answer(request.user, attempt_id, **serializer.validated_data)
        return Response(periodic_attempt_payload(attempt))


class LearnerAdvanceView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def post(self, request, attempt_id):
        serializer = AdvanceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = advance_periodic_attempt(request.user, attempt_id, **serializer.validated_data)
        return Response(periodic_attempt_payload(attempt))


class LearnerSubmitView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def post(self, request, attempt_id):
        attempt = submit_periodic_attempt(request.user, attempt_id)
        return Response(periodic_attempt_payload(attempt))


class LearnerResultView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated, IsExactLearner]

    def get(self, request, attempt_id):
        attempt = get_periodic_attempt(request.user, attempt_id)
        if attempt.submitted_at is None:
            raise PeriodicExamError('This attempt is still in progress.', code='ATTEMPT_IN_PROGRESS')
        return Response({'score_percent': attempt.score_percent, 'passed': attempt.passed})


def _report_organization(request):
    user = request.user
    if user.role == user.Role.ORG_ADMIN and user.organization_id:
        organization = user.organization
    elif user.role == user.Role.PLATFORM_ADMIN:
        organization_id = request.query_params.get('organization_id')
        if not organization_id:
            raise PeriodicExamError(
                'organization_id is required.', code='ORGANIZATION_REQUIRED', status_code=400
            )
        organization = get_object_or_404(Organization, pk=organization_id, is_active=True)
    else:
        raise PeriodicExamError('Permission denied.', code='PERMISSION_DENIED', status_code=403)
    enabled = PeriodicExamSettings.objects.filter(
        organization=organization, enabled=True
    ).exists()
    if not enabled:
        raise PeriodicExamError('Not found.', code='NOT_FOUND', status_code=404)
    return organization


class ReportCycleListView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = _report_organization(request)
        cycles = PeriodicExamCycle.objects.filter(organization=organization).order_by('-starts_at')
        return Response([
            {
                'id': cycle.id,
                'display_label': cycle.display_label,
                'start_date_ad': cycle.start_date_ad,
                'end_date_ad': cycle.end_date_ad,
            }
            for cycle in cycles
        ])


class ReportView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_id, export_format=None):
        organization = _report_organization(request)
        cycle = get_object_or_404(PeriodicExamCycle, pk=cycle_id, organization=organization)
        close_expired_periodic_attempts(cycle=cycle)
        revoke_ineligible_participants(cycle=cycle)
        search = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip()
        queryset = report_participants(cycle, search=search, status_filter=status_filter)
        if export_format == 'csv':
            return csv_report_response(queryset, cycle)
        if export_format == 'xlsx':
            return xlsx_report_response(queryset, cycle)
        try:
            page_number = max(1, int(request.query_params.get('page', 1)))
            page_size = min(200, max(1, int(request.query_params.get('page_size', 50))))
        except (TypeError, ValueError):
            raise PeriodicExamError('Invalid pagination.', code='INVALID_PAGINATION')
        page = Paginator(queryset, page_size).get_page(page_number)
        return Response({
            'count': page.paginator.count,
            'page': page.number,
            'page_size': page_size,
            'results': [row.json() for row in iter_report_rows(page.object_list)],
        })


class ReportHistoryView(PeriodicExamConflictMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, export_format=None):
        organization = _report_organization(request)
        current = ensure_current_cycle(organization)
        if current is not None:
            close_expired_periodic_attempts(cycle=current)
            revoke_ineligible_participants(cycle=current)
        search = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip()
        queryset = report_participants_for_organization(
            organization, search=search, status_filter=status_filter,
        )
        if export_format == 'csv':
            return csv_report_response(queryset, None)
        if export_format == 'xlsx':
            return xlsx_report_response(queryset, None)
        try:
            page_number = max(1, int(request.query_params.get('page', 1)))
            page_size = min(200, max(1, int(request.query_params.get('page_size', 50))))
        except (TypeError, ValueError):
            raise PeriodicExamError('Invalid pagination.', code='INVALID_PAGINATION')
        page = Paginator(queryset, page_size).get_page(page_number)
        return Response({
            'count': page.paginator.count,
            'page': page.number,
            'page_size': page_size,
            'results': [row.json() for row in iter_report_rows(page.object_list)],
        })
