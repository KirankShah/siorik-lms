from django.db import migrations


def normalize_matching_choice_flags(apps, schema_editor):
    Choice = apps.get_model('assessments', 'Choice')
    Choice.objects.filter(question__question_type='MATCHING').update(is_correct=True)


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0013_remove_quiz_pass_percentage'),
    ]

    operations = [
        migrations.RunPython(normalize_matching_choice_flags, migrations.RunPython.noop),
    ]
