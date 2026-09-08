from django.db import migrations

# Backfill: every existing organization gets its four AssessmentLevel rows
# (new orgs get them from the post_save signal in signals.py). Names are the
# four accounts.User.AssessmentLevel codes; pass_threshold / questions_per_attempt
# take the model defaults and are edited per-org by an admin afterwards.
LEVEL_NAMES = ['assistant_supervisor', 'officer', 'management', 'senior_management']


def seed_levels(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    AssessmentLevel = apps.get_model('levelassessments', 'AssessmentLevel')
    for org_id in Organization.objects.values_list('id', flat=True):
        for name in LEVEL_NAMES:
            AssessmentLevel.objects.get_or_create(organization_id=org_id, name=name)


class Migration(migrations.Migration):
    dependencies = [
        ('levelassessments', '0003_alter_assessmentlevel_name'),
        ('accounts', '0007_alter_user_assessment_level'),
    ]

    operations = [
        migrations.RunPython(seed_levels, migrations.RunPython.noop),
    ]
