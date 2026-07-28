from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from accounts.models import User
from courses.models import Course, Lesson, Module

DEMO_INSTRUCTOR_EMAIL = 'demo-instructor@example.com'
DEMO_INSTRUCTOR_PASSWORD = 'DemoPass123!'

DEMO_COURSE_SLUG = 'demo-onboarding-course'

# (module order, module title, lesson order, lesson title, lesson_type, filename, placeholder bytes, estimated_minutes)
DEMO_LESSONS = [
    (1, 'Getting Started', 1, 'Welcome Video', Lesson.LessonType.VIDEO, 'welcome.mp4', b'placeholder video content', 5),
    (1, 'Getting Started', 2, 'Course Slides', Lesson.LessonType.SLIDES, 'course-slides.pdf', b'%PDF-1.4 placeholder slides', 10),
    (2, 'Core Concepts', 1, 'Policy Document', Lesson.LessonType.DOCUMENT, 'policy-document.pdf', b'%PDF-1.4 placeholder document', 15),
    (2, 'Core Concepts', 2, 'Wrap-up Notes', Lesson.LessonType.TEXT, None, None, 5),
]


class Command(BaseCommand):
    help = 'Seeds the database with one demo course, 2 modules, and 4 lessons using placeholder files.'

    def handle(self, *args, **options):
        instructor = self._get_or_create_instructor()
        course, course_created = Course.objects.get_or_create(
            slug=DEMO_COURSE_SLUG,
            defaults={
                'title': 'Demo Onboarding Course',
                'description': 'A sample course seeded for local development and testing.',
                'content_owner': Course.ContentOwner.PLATFORM,
                'is_published': True,
                'created_by': instructor,
            },
        )

        if not course_created:
            self.stdout.write(self.style.WARNING(
                f'Course "{course.title}" already exists (slug="{DEMO_COURSE_SLUG}") - skipping seed.'
            ))
            return

        modules_by_order = {}
        for module_order, module_title, *_ in DEMO_LESSONS:
            if module_order not in modules_by_order:
                modules_by_order[module_order], _ = Module.objects.get_or_create(
                    course=course,
                    order=module_order,
                    defaults={'title': module_title},
                )

        for module_order, _, lesson_order, lesson_title, lesson_type, filename, content_bytes, estimated_minutes in DEMO_LESSONS:
            module = modules_by_order[module_order]
            lesson = Lesson.objects.create(
                module=module,
                order=lesson_order,
                title=lesson_title,
                lesson_type=lesson_type,
                estimated_minutes=estimated_minutes,
            )
            if filename and content_bytes is not None:
                lesson.content_file.save(filename, ContentFile(content_bytes), save=True)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded course "{course.title}" ({course.slug}) with '
            f'{course.modules.count()} modules and '
            f'{Lesson.objects.filter(module__course=course).count()} lessons.'
        ))

    def _get_or_create_instructor(self):
        instructor, created = User.objects.get_or_create(
            email=DEMO_INSTRUCTOR_EMAIL,
            defaults={
                'role': User.Role.INSTRUCTOR,
                'first_name': 'Demo',
                'last_name': 'Instructor',
            },
        )
        if created:
            instructor.set_password(DEMO_INSTRUCTOR_PASSWORD)
            instructor.save()
            self.stdout.write(self.style.SUCCESS(
                f'Created demo instructor: {instructor.email} / {DEMO_INSTRUCTOR_PASSWORD}'
            ))
        return instructor
