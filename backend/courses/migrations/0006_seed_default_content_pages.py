from django.db import migrations


def _build_content_json(lesson):
    """
    Build a minimal BlockNote document that points at the lesson's original
    asset. The asset itself (content_file/content_url) stays on the Lesson
    row untouched — this just gives the new Page something to show.
    """
    text = lesson.title
    if lesson.content_url:
        text = f'{lesson.title} (migrated {lesson.lesson_type} link): {lesson.content_url}'
    elif lesson.content_file:
        text = f'{lesson.title} (migrated {lesson.lesson_type} file): {lesson.content_file.name}'

    return [
        {
            'id': 'migrated-content',
            'type': 'paragraph',
            'props': {},
            'content': [{'type': 'text', 'text': text, 'styles': {}}],
            'children': [],
        }
    ]


def seed_default_content_pages(apps, schema_editor):
    Lesson = apps.get_model('courses', 'Lesson')
    Page = apps.get_model('courses', 'Page')
    PageRevision = apps.get_model('courses', 'PageRevision')

    for lesson in Lesson.objects.all():
        if Page.objects.filter(lesson=lesson).exists():
            continue

        content_json = _build_content_json(lesson)
        page = Page.objects.create(
            lesson=lesson,
            title=lesson.title,
            order=1,
            page_type='CONTENT',
            content_json=content_json,
            estimated_minutes=lesson.estimated_minutes,
        )
        PageRevision.objects.create(page=page, content_json=content_json, edited_by=None)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0005_page_pagerevision_pageprogress'),
    ]

    operations = [
        # Not reversed: collapsing a lesson's pages back into nothing would
        # silently drop any content an instructor has since added.
        migrations.RunPython(seed_default_content_pages, migrations.RunPython.noop),
    ]
