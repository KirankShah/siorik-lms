from django.db import migrations, models
from django.utils import timezone


def mark_existing_badges_as_seen(apps, schema_editor):
    """Do not present historical awards as newly earned after deployment."""
    UserBadge = apps.get_model('gamification', 'UserBadge')
    UserBadge.objects.filter(celebration_seen_at__isnull=True).update(celebration_seen_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ('gamification', '0011_recalculate_leaderboard_scores'),
    ]

    operations = [
        migrations.AddField(
            model_name='userbadge',
            name='celebration_seen_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(mark_existing_badges_as_seen, migrations.RunPython.noop),
    ]
