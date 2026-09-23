from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0012_alter_categorybucket_label_alter_wordbanktoken_text'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='quiz',
            name='pass_percentage',
        ),
    ]
