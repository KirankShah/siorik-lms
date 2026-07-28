# Adds Assignment.slide (nullable) and the new plain-text `instructions`
# field alongside the old page/instructions_json, so the data migration
# (courses 0008) can backfill both before assignments 0003 makes slide
# required and drops page/instructions_json.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0001_initial'),
        ('courses', '0007_slide_element_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='slide',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignment', to='courses.slide'),
        ),
        migrations.AddField(
            model_name='assignment',
            name='instructions',
            field=models.TextField(blank=True, default=''),
        ),
    ]
