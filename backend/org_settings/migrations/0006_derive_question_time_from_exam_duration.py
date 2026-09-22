import math

import django.core.validators
from django.db import migrations, models


def align_existing_assessment_timing(apps, schema_editor):
    OrganizationSettings = apps.get_model('org_settings', 'OrganizationSettings')
    for settings in OrganizationSettings.objects.all().iterator():
        # Preserve the effective duration of existing per-question setups.
        # Fixed-total setups already have the intended duration stored.
        if settings.timing_mode == 'PER_QUESTION':
            settings.total_exam_minutes = max(
                5,
                math.ceil(settings.questions_per_attempt * settings.seconds_per_question / 60),
            )
        settings.timing_mode = 'PER_QUESTION'
        settings.seconds_per_question = max(
            5,
            (settings.total_exam_minutes * 60) // settings.questions_per_attempt,
        )
        settings.save(update_fields=['timing_mode', 'total_exam_minutes', 'seconds_per_question'])


class Migration(migrations.Migration):

    dependencies = [
        ('org_settings', '0005_organizationsettings_max_course_retake_attempts_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organizationsettings',
            name='total_exam_minutes',
            field=models.PositiveIntegerField(
                default=15,
                validators=[django.core.validators.MinValueValidator(5)],
            ),
        ),
        migrations.RunPython(align_existing_assessment_timing, migrations.RunPython.noop),
    ]
