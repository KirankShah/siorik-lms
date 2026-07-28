# Additive: introduces Slide/Element/SlideRevision alongside the existing
# Page/PageRevision/PageProgress models. Page and friends are removed later
# (courses 0009), after assessments/assignments have been repointed at Slide
# and a data migration has copied existing content across.
import courses.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_seed_default_content_pages'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Slide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, default='', max_length=255)),
                ('order', models.PositiveIntegerField(default=0)),
                ('slide_type', models.CharField(choices=[('CONTENT', 'Content'), ('QUIZ', 'Quiz'), ('ASSIGNMENT', 'Assignment')], default='CONTENT', max_length=20)),
                ('estimated_minutes', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slides', to='courses.lesson')),
            ],
            options={
                'ordering': ['order'],
                'unique_together': {('lesson', 'order')},
            },
        ),
        migrations.CreateModel(
            name='Element',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('element_type', models.CharField(choices=[('TEXT', 'Text'), ('IMAGE', 'Image'), ('VIDEO_AUDIO', 'Video/Audio'), ('BREAKOUT_IMAGE', 'Breakout image'), ('QUOTE', 'Quote'), ('FILE_DOWNLOAD', 'File download'), ('EMBED', 'Embed'), ('PRESENTATION_PDF', 'Presentation/PDF')], default='TEXT', max_length=20)),
                ('rich_text', models.TextField(blank=True, default='')),
                ('file', models.FileField(blank=True, null=True, upload_to='element_files/', validators=[courses.validators.validate_lesson_file_size])),
                ('video_url', models.URLField(blank=True, default='')),
                ('video_file', models.FileField(blank=True, null=True, upload_to='element_videos/', validators=[courses.validators.validate_lesson_file_size])),
                ('embed_url', models.URLField(blank=True, default='')),
                ('caption', models.CharField(blank=True, default='', max_length=500)),
                ('slide', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements', to='courses.slide')),
            ],
            options={
                'ordering': ['order'],
                'unique_together': {('slide', 'order')},
            },
        ),
        migrations.CreateModel(
            name='SlideRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('elements_json', models.JSONField(blank=True, default=list)),
                ('edited_at', models.DateTimeField(auto_now_add=True)),
                ('edited_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='slide_revisions', to=settings.AUTH_USER_MODEL)),
                ('slide', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='courses.slide')),
            ],
            options={
                'ordering': ['-edited_at'],
            },
        ),
        migrations.CreateModel(
            name='SlideProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('time_spent_seconds', models.PositiveIntegerField(default=0)),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='slide_progress', to='courses.enrollment')),
                ('slide', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_entries', to='courses.slide')),
            ],
            options={
                'ordering': ['slide__order'],
                'unique_together': {('enrollment', 'slide')},
            },
        ),
    ]
