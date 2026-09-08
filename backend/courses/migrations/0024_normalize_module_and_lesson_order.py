from django.db import migrations

# Companion to 0023 (which did the same for Slide.order). A course cloned via
# clone_course copies every module's and lesson's `order` verbatim; deleting
# the first few modules/lessons then left the survivors at order 6, 7, 8, ...
# with nothing to renumber them (perform_destroy does now). The stale values
# show directly as the "N." prefixes in the curriculum editor, and "add
# module"/"add lesson" — which appended at max(order) + 1 — collided with a
# surviving row through the (course, order) / (module, order) unique_together.
#
# Rewrite every course's modules and every module's lessons to a contiguous
# 1..N, preserving relative order. Two-phase to avoid the unique_together.

TEMP_OFFSET = 100_000


def _renumber(model, group_field, group_ids):
    for group_id in group_ids:
        rows = list(
            model.objects.filter(**{group_field: group_id}).order_by('order', 'id').values_list('id', 'order')
        )
        if all(order == index for index, (_pk, order) in enumerate(rows, start=1)):
            continue  # already 1..N
        pks = [pk for pk, _order in rows]
        for offset, pk in enumerate(pks):
            model.objects.filter(pk=pk).update(order=TEMP_OFFSET + offset)
        for index, pk in enumerate(pks, start=1):
            model.objects.filter(pk=pk).update(order=index)


def normalize_module_and_lesson_order(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    Module = apps.get_model('courses', 'Module')
    Lesson = apps.get_model('courses', 'Lesson')

    _renumber(Module, 'course_id', list(Course.objects.values_list('id', flat=True)))
    _renumber(Lesson, 'module_id', list(Module.objects.values_list('id', flat=True)))


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0023_normalize_slide_order'),
    ]

    operations = [
        migrations.RunPython(normalize_module_and_lesson_order, migrations.RunPython.noop),
    ]
