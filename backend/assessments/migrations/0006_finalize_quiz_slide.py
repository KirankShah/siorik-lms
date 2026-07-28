import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0005_quiz_slide_nullable'),
        ('courses', '0008_migrate_page_content_to_slides'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quiz',
            name='slide',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quizzes', to='courses.slide'),
        ),
        migrations.AlterModelOptions(
            name='quiz',
            options={'ordering': ['slide', 'title']},
        ),
        migrations.RemoveField(
            model_name='quiz',
            name='page',
        ),
    ]
