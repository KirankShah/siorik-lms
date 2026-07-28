from django.db import migrations

BADGES = [
    ('first_course_complete', 'First Course Complete', 'Completed your first course.', '🎓'),
    ('five_courses_complete', '5 Courses Complete', 'Completed five courses.', '🏆'),
    ('perfect_score', 'Perfect Score', 'Scored 100% on a quiz.', '💯'),
    ('high_achiever', 'High Achiever', 'Maintained a 90%+ average quiz score across at least 3 quizzes.', '⭐'),
]


def seed_badges(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    for key, name, description, icon in BADGES:
        Badge.objects.get_or_create(key=key, defaults={'name': name, 'description': description, 'icon': icon})


def remove_badges(apps, schema_editor):
    Badge = apps.get_model('gamification', 'Badge')
    Badge.objects.filter(key__in=[key for key, *_ in BADGES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_badges, remove_badges),
    ]
