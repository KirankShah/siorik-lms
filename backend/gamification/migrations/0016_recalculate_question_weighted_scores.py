from django.db import migrations


def recalculate_question_weighted_scores(apps, schema_editor):
    # Use the live service so this one-time data refresh follows the same
    # learning-path and latest-attempt rules as future event-driven updates.
    from accounts.models import User
    from gamification.models import LeaderboardEntry
    from gamification.services import recalculate_leaderboard_entry

    learner_ids = list(
        LeaderboardEntry.objects.order_by().values_list('user_id', flat=True)
    )
    for learner in User.objects.filter(id__in=learner_ids).iterator():
        recalculate_leaderboard_entry(learner)


class Migration(migrations.Migration):
    dependencies = [
        ('gamification', '0015_leaderboard_quiz_coverage'),
    ]

    operations = [
        migrations.RunPython(
            recalculate_question_weighted_scores,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
