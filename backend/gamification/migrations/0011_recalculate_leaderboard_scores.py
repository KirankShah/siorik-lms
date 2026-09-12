from django.db import migrations


def recalculate_all_leaderboard_entries(apps, schema_editor):
    """
    Refreshes every EXISTING LeaderboardEntry under the corrected formula
    (course-completion points scoped to the learner's own assigned Learning
    Path; the level-assessment bonus scaled by each passed level's own best
    score instead of a flat award) immediately, rather than leaving stale
    rows sitting until each learner's next course completion/quiz attempt/
    level assessment submission happens to trigger a recompute.

    Deliberately imports the real, current accounts.models.User and
    gamification.services.recalculate_leaderboard_entry — not the
    historical/frozen apps.get_model versions migrations normally use —
    since "recalculate under the corrected formula" inherently means
    running today's actual formula code, not a snapshot of it frozen at
    whatever point this migration was written.
    """
    from accounts.models import User
    from gamification.models import LeaderboardEntry
    from gamification.services import recalculate_leaderboard_entry

    user_ids = list(LeaderboardEntry.objects.values_list('user_id', flat=True))
    for user in User.objects.filter(id__in=user_ids):
        recalculate_leaderboard_entry(user)


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0010_fix_mysql_latin1_charset'),
    ]

    operations = [
        # Recomputing under a corrected formula isn't something a reverse
        # migration can sensibly "undo" (there's no way to restore the
        # old, incorrect point totals as data worth going back to).
        migrations.RunPython(recalculate_all_leaderboard_entries, migrations.RunPython.noop),
    ]
