from rest_framework import serializers

from .models import Badge, LeaderboardEntry, UserBadge


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    # Deliberately exposes just enough to render a leaderboard row — no
    # email/role/other account details.
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = LeaderboardEntry
        fields = [
            'user_id',
            'first_name',
            'last_name',
            'total_points',
            'courses_completed_count',
            'average_quiz_score',
            'updated_at',
        ]


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'key', 'name', 'description', 'icon']


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ['id', 'badge', 'earned_at']
