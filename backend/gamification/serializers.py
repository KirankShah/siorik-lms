from rest_framework import serializers

from .models import Badge, LeaderboardEntry, UserBadge


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    # Deliberately exposes just enough to render a leaderboard row — no
    # email/role/other account details.
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    assessment_level = serializers.CharField(source='user.assessment_level', read_only=True)
    assessment_level_display = serializers.SerializerMethodField()
    is_ranked = serializers.SerializerMethodField()

    def get_assessment_level_display(self, obj):
        return obj.user.get_assessment_level_display() if obj.user.assessment_level else ''

    def get_is_ranked(self, obj):
        return obj.knowledge_score is not None

    class Meta:
        model = LeaderboardEntry
        fields = [
            'user_id',
            'first_name',
            'last_name',
            'assessment_level',
            'assessment_level_display',
            'total_points',
            'courses_completed_count',
            'average_quiz_score',
            'current_course_quiz_average',
            'quizzes_completed',
            'quizzes_required',
            'latest_level_assessment_score',
            'knowledge_score',
            'is_ranked',
            'last_assessed_at',
            'certificates_earned_count',
            'level_assessments_passed_count',
            'updated_at',
        ]


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'key', 'name', 'description', 'icon', 'unlock_condition']


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ['id', 'badge', 'earned_at', 'celebration_seen_at']
