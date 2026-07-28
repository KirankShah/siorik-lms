from django.contrib import admin

from .models import Badge, LeaderboardEntry, UserBadge


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'total_points', 'courses_completed_count', 'average_quiz_score', 'updated_at')
    list_filter = ('organization',)
    search_fields = ('user__email',)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'icon')
    search_fields = ('key', 'name')


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')
    list_filter = ('badge',)
    search_fields = ('user__email',)
