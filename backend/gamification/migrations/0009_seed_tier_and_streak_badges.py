from django.db import migrations

# Mirrors courses.learning_path.TIER_COMPLETE_BADGE_KEYS — one badge per tier
# a learner's Learning Path can include. Awarded from
# courses.learning_path.check_learning_path_milestones the moment every
# course in that tier is completed.
TIER_BADGES = [
    (
        'tier_complete_foundation',
        'Foundation Complete',
        "Completed every course in your Learning Path's Foundation tier.",
        '🏁',
        "Complete every course in your Learning Path's Foundation tier to unlock this achievement.",
    ),
    (
        'tier_complete_assistant_supervisor',
        'Assistant-Supervisor Track Complete',
        "Completed every course in your Learning Path's Assistant-Supervisor tier.",
        '🎖️',
        "Complete every course in your Learning Path's Assistant-Supervisor tier to unlock this achievement.",
    ),
    (
        'tier_complete_officer',
        'Officer Track Complete',
        "Completed every course in your Learning Path's Officer tier.",
        '🎖️',
        "Complete every course in your Learning Path's Officer tier to unlock this achievement.",
    ),
    (
        'tier_complete_management',
        'Management Track Complete',
        "Completed every course in your Learning Path's Management tier.",
        '🎖️',
        "Complete every course in your Learning Path's Management tier to unlock this achievement.",
    ),
    (
        'tier_complete_senior_management',
        'Senior Management Track Complete',
        "Completed every course in your Learning Path's Senior Management tier.",
        '🎖️',
        "Complete every course in your Learning Path's Senior Management tier to unlock this achievement.",
    ),
]

# Mirrors gamification.services.STREAK_BADGE_THRESHOLDS — a longer streak
# added there later (7-day, 30-day, ...) needs its own row added here the
# same way.
STREAK_BADGES = [
    (
        'streak_3_day',
        '3-Day Streak',
        'Made learning progress on 3 consecutive days.',
        '🔥',
        'Make learning progress (a slide, a quiz, or a course) on 3 days in a row to unlock this achievement.',
    ),
]

ALL_BADGES = TIER_BADGES + STREAK_BADGES


def seed_badges(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    for key, name, description, icon, unlock_condition in ALL_BADGES:
        Badge.objects.get_or_create(
            key=key,
            defaults={'name': name, 'description': description, 'icon': icon, 'unlock_condition': unlock_condition},
        )


def remove_badges(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    Badge.objects.filter(key__in=[key for key, *_ in ALL_BADGES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0008_leaderboardentry_level_assessments_passed_count'),
    ]

    operations = [
        migrations.RunPython(seed_badges, remove_badges),
    ]
