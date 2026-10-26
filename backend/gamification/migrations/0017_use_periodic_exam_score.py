from django.db import migrations


def recalculate_periodic_exam_scores(apps, schema_editor):
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
        ('gamification', '0016_recalculate_question_weighted_scores'),
        ('periodic_exams', '0004_periodicexamreminderdelivery'),
    ]

    operations = [
        migrations.RenameField(
            model_name='leaderboardentry',
            old_name='latest_level_assessment_score',
            new_name='latest_periodic_exam_score',
        ),
        migrations.RunPython(
            recalculate_periodic_exam_scores,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
