from django.db import migrations


def set_matching_is_correct(apps, schema_editor):
    Choice = apps.get_model('assessments', 'Choice')
    Choice.objects.filter(question__question_type='MATCHING', is_correct=False).update(is_correct=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0006_finalize_quiz_slide'),
    ]

    operations = [
        migrations.RunPython(set_matching_is_correct, noop),
    ]
