from django.db import migrations

# Backfill: every existing organization gets its OrganizationSettings row
# (new orgs get theirs from the post_save signal in signals.py). Values take
# the model defaults (questions_per_attempt=15, seconds_per_question=60,
# pass_mark_percent=70) — matching the AssessmentLevel/Course defaults they
# replace — and are edited per-org by an admin afterwards from the
# Organization Settings screen.
def seed_settings(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    OrganizationSettings = apps.get_model('org_settings', 'OrganizationSettings')
    for org_id in Organization.objects.values_list('id', flat=True):
        OrganizationSettings.objects.get_or_create(organization_id=org_id)


class Migration(migrations.Migration):
    dependencies = [
        ('org_settings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_settings, migrations.RunPython.noop),
    ]
