from django.db import migrations, models
import periodic_exams.models


def use_fixed_notifications(apps, schema_editor):
    Settings = apps.get_model('periodic_exams', 'PeriodicExamSettings')
    Cycle = apps.get_model('periodic_exams', 'PeriodicExamCycle')
    Settings.objects.update(reminders_enabled=True, reminder_days_before_end=[7])
    Cycle.objects.update(reminders_enabled=True, reminder_days_before_end=[7])


class Migration(migrations.Migration):

    dependencies = [
        ('periodic_exams', '0004_periodicexamreminderdelivery'),
    ]

    operations = [
        migrations.AlterField(
            model_name='periodicexamsettings',
            name='reminders_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='periodicexamsettings',
            name='reminder_days_before_end',
            field=models.JSONField(default=periodic_exams.models.default_reminder_days),
        ),
        migrations.RunPython(use_fixed_notifications, migrations.RunPython.noop),
    ]
