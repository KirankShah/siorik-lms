# Adds Quiz.slide as nullable so the data migration (courses 0008) can
# backfill it from the old Quiz.page before it's made required and Quiz.page
# is dropped (assessments 0006).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0004_alter_choice_options_choice_match_text_choice_order_and_more'),
        ('courses', '0007_slide_element_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='quiz',
            name='slide',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='quizzes', to='courses.slide'),
        ),
    ]
