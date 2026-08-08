from django.db import migrations


def backfill_certificates_earned_count(apps, schema_editor):
    from django.db.models import Count

    LeaderboardEntry = apps.get_model('gamification', 'LeaderboardEntry')
    Certificate = apps.get_model('certificates', 'Certificate')

    counts = dict(
        Certificate.objects.values('user_id').annotate(count=Count('id')).values_list('user_id', 'count')
    )

    entries = list(LeaderboardEntry.objects.all())
    for entry in entries:
        entry.certificates_earned_count = counts.get(entry.user_id, 0)
    LeaderboardEntry.objects.bulk_update(entries, ['certificates_earned_count'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0003_leaderboardentry_certificates_earned_count'),
        ('certificates', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_certificates_earned_count, noop_reverse),
    ]
