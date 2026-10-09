from django.db import migrations


def recalculate_existing_entries(apps, schema_editor):
    from accounts.models import User
    from gamification.models import LeaderboardEntry
    from gamification.services import recalculate_leaderboard_entry

    user_ids = list(LeaderboardEntry.objects.values_list('user_id', flat=True))
    for user in User.objects.filter(id__in=user_ids).iterator():
        recalculate_leaderboard_entry(user)


class Migration(migrations.Migration):
    dependencies = [('gamification', '0013_leaderboard_current_knowledge')]

    operations = [
        migrations.RunPython(recalculate_existing_entries, migrations.RunPython.noop),
    ]
