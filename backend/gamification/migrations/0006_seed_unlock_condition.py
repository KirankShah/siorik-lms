from django.db import migrations

# Mirrors the actual thresholds checked in gamification.services.award_badges_for_user.
UNLOCK_CONDITIONS = {
    'first_course_complete': 'Complete 1 course to unlock this achievement.',
    'five_courses_complete': 'Complete 5 courses to unlock this achievement.',
    'perfect_score': 'Score 100% on any quiz to unlock this achievement.',
    'high_achiever': 'Maintain a 90%+ average score across at least 3 quizzes to unlock this achievement.',
}


def seed_unlock_conditions(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    for key, unlock_condition in UNLOCK_CONDITIONS.items():
        Badge.objects.filter(key=key).update(unlock_condition=unlock_condition)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0005_badge_unlock_condition'),
    ]

    operations = [
        migrations.RunPython(seed_unlock_conditions, noop_reverse),
    ]
