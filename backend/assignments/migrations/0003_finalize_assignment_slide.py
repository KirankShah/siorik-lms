import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0002_assignment_slide_and_instructions'),
        ('courses', '0008_migrate_page_content_to_slides'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignment',
            name='slide',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='assignment', to='courses.slide'),
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='page',
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='instructions_json',
        ),
    ]
