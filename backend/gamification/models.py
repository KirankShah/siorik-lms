from django.conf import settings
from django.db import models

from accounts.models import Organization


class LeaderboardEntry(models.Model):
    """
    One row per user, recalculated (not computed live) whenever a course is
    completed or a quiz is attempted — see gamification.services. A plain
    OneToOne rather than a repeated FK, since "recalculated" implies upsert:
    there is exactly one current standing per user.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaderboard_entry')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='leaderboard_entries')
    total_points = models.PositiveIntegerField(default=0)
    courses_completed_count = models.PositiveIntegerField(default=0)
    average_quiz_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    # Recalculated alongside the other fields, on certificate generation (see
    # certificates.services.generate_certificate) rather than computed live.
    certificates_earned_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_points', '-average_quiz_score']

    def __str__(self):
        return f'{self.user} - {self.total_points} pts'


class Badge(models.Model):
    """Definitions are seeded by a data migration — see 0002_seed_badges."""

    key = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, default='')
    icon = models.CharField(max_length=10, blank=True, default='', help_text='A single emoji shown next to the badge.')
    # Learner-facing copy for the not-yet-earned state, e.g. "Complete 5
    # courses to unlock." Mirrors the actual condition checked in
    # gamification.services.award_badges_for_user for this badge's key.
    unlock_condition = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awarded_to')
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')
        ordering = ['-earned_at']

    def __str__(self):
        return f'{self.user} - {self.badge}'
