import json

from django.db import migrations


def _extract_text(blocknote_json):
    """
    Best-effort flattening of a BlockNote document (list of block dicts) into
    plain text, since the new Element.rich_text/Assignment.instructions are
    plain TextFields rather than block-structured JSON. Falls back to a raw
    JSON dump for any block shape this doesn't recognize, so content is
    preserved even if formatting isn't.
    """
    if not blocknote_json:
        return ''

    lines = []

    def walk(blocks):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            texts = [
                inline.get('text', '')
                for inline in block.get('content', []) or []
                if isinstance(inline, dict)
            ]
            line = ''.join(texts).strip()
            if line:
                lines.append(line)
            children = block.get('children')
            if children:
                walk(children)

    try:
        walk(blocknote_json)
    except (AttributeError, TypeError):
        lines = []

    if lines:
        return '\n'.join(lines)

    # Nothing recognizable extracted (custom block types, empty doc, etc.) —
    # keep the original content as a JSON dump rather than silently dropping it.
    try:
        return json.dumps(blocknote_json, ensure_ascii=False)
    except TypeError:
        return ''


def migrate_page_content_to_slides(apps, schema_editor):
    Lesson = apps.get_model('courses', 'Lesson')
    Page = apps.get_model('courses', 'Page')
    Slide = apps.get_model('courses', 'Slide')
    Element = apps.get_model('courses', 'Element')
    SlideRevision = apps.get_model('courses', 'SlideRevision')
    Quiz = apps.get_model('assessments', 'Quiz')
    Assignment = apps.get_model('assignments', 'Assignment')

    page_id_to_slide = {}

    for page in Page.objects.all():
        slide = Slide.objects.create(
            lesson_id=page.lesson_id,
            title=page.title,
            order=page.order,
            slide_type=page.page_type,
            estimated_minutes=page.estimated_minutes,
        )
        page_id_to_slide[page.id] = slide

        rich_text = _extract_text(page.content_json)
        element = Element.objects.create(
            slide=slide,
            order=1,
            element_type='TEXT',
            rich_text=rich_text,
        )
        SlideRevision.objects.create(
            slide=slide,
            elements_json=[{
                'id': element.id,
                'order': element.order,
                'element_type': element.element_type,
                'rich_text': element.rich_text,
                'file': None,
                'video_url': '',
                'video_file': None,
                'embed_url': '',
                'caption': '',
            }],
            edited_by=None,
        )

    # Defensive fallback for any Lesson that (unexpectedly) has no Page at
    # all — mirrors the original Lesson -> Page seed migration.
    for lesson in Lesson.objects.all():
        if Slide.objects.filter(lesson=lesson).exists():
            continue

        if lesson.content_url:
            text = f'{lesson.title} (migrated {lesson.lesson_type} link): {lesson.content_url}'
        elif lesson.content_file:
            text = f'{lesson.title} (migrated {lesson.lesson_type} file): {lesson.content_file.name}'
        else:
            text = lesson.title

        slide = Slide.objects.create(
            lesson=lesson,
            title=lesson.title,
            order=1,
            slide_type='CONTENT',
            estimated_minutes=lesson.estimated_minutes,
        )
        element = Element.objects.create(slide=slide, order=1, element_type='TEXT', rich_text=text)
        SlideRevision.objects.create(
            slide=slide,
            elements_json=[{
                'id': element.id,
                'order': element.order,
                'element_type': element.element_type,
                'rich_text': element.rich_text,
                'file': None,
                'video_url': '',
                'video_file': None,
                'embed_url': '',
                'caption': '',
            }],
            edited_by=None,
        )

    for quiz in Quiz.objects.all():
        slide = page_id_to_slide.get(quiz.page_id)
        if slide is not None:
            quiz.slide = slide
            quiz.save(update_fields=['slide'])

    for assignment in Assignment.objects.all():
        slide = page_id_to_slide.get(assignment.page_id)
        if slide is not None:
            assignment.slide = slide
        assignment.instructions = _extract_text(assignment.instructions_json)
        assignment.save(update_fields=['slide', 'instructions'])


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0007_slide_element_models'),
        ('assessments', '0005_quiz_slide_nullable'),
        ('assignments', '0002_assignment_slide_and_instructions'),
    ]

    operations = [
        # Not reversed: this is a one-way content migration off the old
        # Page/content_json model, same policy as the original Lesson -> Page
        # seed migration it supersedes.
        migrations.RunPython(migrate_page_content_to_slides, migrations.RunPython.noop),
    ]
