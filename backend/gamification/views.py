from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

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
            LeaderboardEntry.objects.filter(organization_id=user.organization_id)
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
