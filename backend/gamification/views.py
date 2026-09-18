from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Badge, LeaderboardEntry, UserBadge
from .serializers import BadgeSerializer, LeaderboardEntrySerializer, UserBadgeSerializer


class LeaderboardEntryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Read-only, organization-scoped standings. The organization filter is
    enforced here at the queryset level (not just hidden in the UI), so a
    direct API call can never see another tenant's leaderboard.
    """

    serializer_class = LeaderboardEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.organization_id is None:
            return LeaderboardEntry.objects.none()
        return (
            LeaderboardEntry.objects.filter(organization_id=user.organization_id, user__is_active=True)
            .select_related('user')
            .order_by('-total_points', '-average_quiz_score')
        )


class BadgeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Global badge definitions — same for every organization."""

    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    permission_classes = [IsAuthenticated]


class UserBadgeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Always scoped to the caller's own badges — no way to query someone else's."""

    serializer_class = UserBadgeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserBadge.objects.filter(user=self.request.user).select_related('badge')

    @action(detail=True, methods=['post'], url_path='acknowledge-celebration')
    def acknowledge_celebration(self, request, pk=None):
        """Marks one of the caller's badge celebrations as seen.

        get_object() uses the user-scoped queryset above, so a learner cannot
        acknowledge (or discover) another learner's award by guessing an id.
        The operation is deliberately idempotent for retries and double-clicks.
        """
        user_badge = self.get_object()
        if user_badge.celebration_seen_at is None:
            user_badge.celebration_seen_at = timezone.now()
            user_badge.save(update_fields=['celebration_seen_at'])
        return Response(self.get_serializer(user_badge).data)
