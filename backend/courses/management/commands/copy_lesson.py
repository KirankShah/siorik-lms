from django.core.management.base import BaseCommand, CommandError

from courses.models import Course, Lesson
from courses.services import copy_lesson


class Command(BaseCommand):
    help = (
        'Copies a single Lesson (with its Slides/Elements/Quiz/Assignment/Scenario/'
        'Narration content) from its source course into the matching Module (by title) '
        'of a target course. Intended for backfilling a lesson added to a platform '
        'master course into org course clones that were forked before the lesson existed '
        '- clone_course only runs once at fork time and never re-syncs.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--lesson-id', type=int, help='Source Lesson id to copy.')
        parser.add_argument(
            '--lesson-title', type=str,
            help='Source lesson title (used with --source-course-slug if the title is ambiguous).',
        )
        parser.add_argument('--source-course-slug', type=str, help='Slug of the course the lesson currently lives in.')
        parser.add_argument('--target-course-slug', type=str, required=True, help='Slug of the destination course.')
        parser.add_argument(
            '--target-module-title', type=str,
            help='Title of the destination module. Defaults to the source lesson\'s own module title.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Report what would happen without writing anything.')

    def handle(self, *args, **options):
        lesson = self._resolve_lesson(options)
        target_course = self._resolve_course(options['target_course_slug'])
        target_module_title = options.get('target_module_title') or lesson.module.title
        target_module = target_course.modules.filter(title=target_module_title).first()
        if target_module is None:
            raise CommandError(
                f'Target course "{target_course.title}" (slug={target_course.slug}) has no module '
                f'titled "{target_module_title}". Existing modules: '
                f'{list(target_course.modules.order_by("order").values_list("title", flat=True))}'
            )

        if Lesson.objects.filter(module=target_module, title=lesson.title).exists():
            raise CommandError(
                f'Module "{target_module.title}" in course "{target_course.title}" already has a '
                f'lesson titled "{lesson.title}" - refusing to create a duplicate.'
            )

        self.stdout.write(
            f'Copying lesson "{lesson.title}" (id={lesson.id}) from course '
            f'"{lesson.module.course.title}" -> course "{target_course.title}", module "{target_module.title}" '
            f'({lesson.slides.count()} slide(s)).'
        )

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('--dry-run given, no changes made.'))
            return

        cloned = copy_lesson(lesson, target_module)
        self.stdout.write(self.style.SUCCESS(
            f'Created lesson id={cloned.id} "{cloned.title}" in module id={target_module.id} '
            f'(order={cloned.order}).'
        ))

    def _resolve_lesson(self, options):
        lesson_id = options.get('lesson_id')
        lesson_title = options.get('lesson_title')
        source_course_slug = options.get('source_course_slug')

        if lesson_id:
            try:
                return Lesson.objects.get(id=lesson_id)
            except Lesson.DoesNotExist:
                raise CommandError(f'No Lesson with id={lesson_id}.')

        if not lesson_title:
            raise CommandError('Provide either --lesson-id or --lesson-title.')

        qs = Lesson.objects.filter(title=lesson_title)
        if source_course_slug:
            qs = qs.filter(module__course__slug=source_course_slug)

        matches = list(qs)
        if not matches:
            raise CommandError(f'No lesson titled "{lesson_title}" found' + (
                f' in course slug={source_course_slug}.' if source_course_slug else '.'
            ))
        if len(matches) > 1:
            locations = ', '.join(f'id={l.id} (course={l.module.course.slug})' for l in matches)
            raise CommandError(
                f'Multiple lessons titled "{lesson_title}" found: {locations}. '
                'Disambiguate with --lesson-id or --source-course-slug.'
            )
        return matches[0]

    def _resolve_course(self, slug):
        try:
            return Course.objects.get(slug=slug)
        except Course.DoesNotExist:
            raise CommandError(f'No Course with slug="{slug}".')
