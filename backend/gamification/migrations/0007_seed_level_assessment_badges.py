from django.db import migrations

# Mirrors the conditions checked in gamification.services.award_badges_for_level_assessment_attempt.
NEW_BADGES = [
    (
        'first_strike',
        'First Strike',
        'Answered an assessment question correctly on your very first attempt.',
        '🎯',
        'Get at least one question right on your first-ever level assessment attempt to unlock this achievement.',
    ),
    (
        'hat_trick',
        'Hat Trick',
        'Answered three assessment questions correctly in a row.',
        '🎩',
        'Answer three questions correctly in a row within a single level assessment attempt to unlock this achievement.',
    ),
    (
        'comeback',
        'Comeback',
        'Passed a level assessment on a retake after a previous failed attempt.',
        '🔥',
        'Pass a level assessment after failing a previous attempt at the same level to unlock this achievement.',
    ),
    (
        'branch_pride',
        'Branch Pride',
        'First in your branch/department to pass your assigned level assessment.',
        '🏅',
        'Be the first person in your branch/department to pass your assigned level assessment to unlock this achievement.',
    ),
]

# 'perfect_score' already exists (seeded quiz-only in 0002/0006) — broadened
# here to also cover level assessments, rather than adding a second
# same-named badge for what is, for a learner, the same achievement.
PERFECT_SCORE_BROADENED = {
    'description': 'Scored 100% on a quiz or level assessment.',
    'unlock_condition': 'Score 100% on any quiz or level assessment to unlock this achievement.',
}
PERFECT_SCORE_QUIZ_ONLY = {
    'description': 'Scored 100% on a quiz.',
    'unlock_condition': 'Score 100% on any quiz to unlock this achievement.',
}


def seed_badges(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    for key, name, description, icon, unlock_condition in NEW_BADGES:
        Badge.objects.get_or_create(
            key=key,
            defaults={'name': name, 'description': description, 'icon': icon, 'unlock_condition': unlock_condition},
        )
    Badge.objects.filter(key='perfect_score').update(**PERFECT_SCORE_BROADENED)


def reverse_seed_badges(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    Badge.objects.filter(key__in=[key for key, *_ in NEW_BADGES]).delete()
    Badge.objects.filter(key='perfect_score').update(**PERFECT_SCORE_QUIZ_ONLY)


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0006_seed_unlock_condition'),
    ]

    operations = [
        migrations.RunPython(seed_badges, reverse_seed_badges),
    ]
