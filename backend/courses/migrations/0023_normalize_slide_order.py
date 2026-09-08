from django.db import migrations

# One-time cleanup for lessons whose slide `order` sequence has gaps — e.g. a
# course cloned (clone_course copies order verbatim) and then had its first few
# slides deleted, leaving the survivors at order 6, 7, 8, ... Deletion didn't
# renumber them (it does now, see SlideViewSet.perform_destroy), so "add slide"
# — which appends at max(order) + 1 — and the displayed "Slide N" labels drifted.
#
# This rewrites every lesson's slides to a contiguous 1..N, preserving their
# existing relative order. Two-phase (bump into a high temp range first) to
# avoid tripping Slide's (lesson, order) unique_together mid-update.

TEMP_OFFSET = 100_000


def normalize_slide_order(apps, schema_editor):
    Slide = apps.get_model('courses', 'Slide')
    Lesson = apps.get_model('courses', 'Lesson')

    for lesson_id in Lesson.objects.values_list('id', flat=True):
        rows = list(
            Slide.objects.filter(lesson_id=lesson_id).order_by('order', 'id').values_list('id', 'order')
        )
        if all(order == index for index, (_slide_id, order) in enumerate(rows, start=1)):
            continue  # already 1..N

        slide_ids = [slide_id for slide_id, _order in rows]
        for offset, slide_id in enumerate(slide_ids):
            Slide.objects.filter(pk=slide_id).update(order=TEMP_OFFSET + offset)
        for index, slide_id in enumerate(slide_ids, start=1):
            Slide.objects.filter(pk=slide_id).update(order=index)


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0022_course_cloned_from'),
    ]

    operations = [
        # Data-only fix; nothing to undo (the old gapped numbering carried no
        # meaning), so the reverse is a no-op.
        migrations.RunPython(normalize_slide_order, migrations.RunPython.noop),
    ]
