from django.db import migrations, models


def recalculate_existing_entries(apps, schema_editor):
    # Match the established recalculation migration pattern in 0011: fields
    # are present before this runs, and the service is the single source of
    # truth for both live updates and this one-time production backfill.
    from accounts.models import User
    from gamification.models import LeaderboardEntry
    from gamification.services import recalculate_leaderboard_entry

    user_ids = list(LeaderboardEntry.objects.values_list('user_id', flat=True))
    for user in User.objects.filter(id__in=user_ids).iterator():
        recalculate_leaderboard_entry(user)


class Migration(migrations.Migration):
    dependencies = [('gamification', '0012_userbadge_celebration_seen_at')]

    operations = [
        migrations.AddField(
            model_name='leaderboardentry',
            name='current_course_quiz_average',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='leaderboardentry',
            name='latest_level_assessment_score',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='leaderboardentry',
            name='knowledge_score',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='leaderboardentry',
            name='last_assessed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name='leaderboardentry',
            options={'ordering': ['-knowledge_score', '-current_course_quiz_average', '-last_assessed_at']},
        ),
        migrations.RunPython(recalculate_existing_entries, migrations.RunPython.noop),
    ]
