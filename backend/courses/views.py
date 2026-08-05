import csv
import io
import uuid
from pathlib import PurePosixPath

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Organization, User
from assessments.models import QuizAttempt
from audit.models import AuditLog
from audit.services import log_action
from core.permissions import IsAdminRole, RoleScopedQuerysetMixin
from gamification.services import update_gamification_for_user

from .models import (
    Course,
    CourseAccess,
    Element,
    Enrollment,
    Lesson,
    LessonProgress,
    Module,
    Slide,
    SlideProgress,
    SlideTemplate,
)
from .permissions import editable_courses_for_user, visible_courses_for_user
from .serializers import (
    CourseAccessSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
    CourseWriteSerializer,
    ElementSerializer,
    EnrollmentSerializer,
    LessonOrderSerializer,
    LessonWriteSerializer,
    ModuleOrderSerializer,
    ModuleWriteSerializer,
    SlideProgressSerializer,
    SlideSerializer,
    SlideSummarySerializer,
    SlideTemplateSerializer,
)
from .validators import MAX_LESSON_FILE_SIZE_BYTES

# Order values are bumped into this range as a first pass during a reorder,
# so that reassigning final 1..N values never collides with an order another
# slide in the same lesson still holds — Slide has a unique_together on
# (lesson, order), enforced at the DB level.
REORDER_TEMP_OFFSET = 10_000

WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')

# Prevents CSV/formula injection: a cell starting with =, +, -, or @ can be
# interpreted as a formula (and executed) when the file is opened in Excel.
_FORMULA_PREFIXES = ('=', '+', '-', '@')


def _csv_safe(value):
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


class CourseViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'

    ACCESS_GRANT_ACTIONS = ('access_grants', 'revoke_access')

    def get_permissions(self):
        if (
            self.action in WRITE_ACTIONS
            or self.action in ('bulk_enroll', 'invite')
            or self.action in self.ACCESS_GRANT_ACTIONS
        ):
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if self.action in ('list', 'retrieve'):
            return visible_courses_for_user(self.request.user)
        return editable_courses_for_user(self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        if self.action in WRITE_ACTIONS:
            return CourseWriteSerializer
        return CourseDetailSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == User.Role.PLATFORM_ADMIN:
            # PLATFORM_ADMIN-authored courses are always platform-owned, regardless
            # of whatever organization value (if any) they attach as metadata.
            course = serializer.save(created_by=user, content_owner=Course.ContentOwner.PLATFORM)
        else:
            # ORG_ADMIN/INSTRUCTOR can only author self-serve content scoped to
            # their own org — both fields are forced, ignoring the request body.
            course = serializer.save(created_by=user, content_owner=Course.ContentOwner.ORGANIZATION, organization=user.organization)
        log_action(user, AuditLog.Action.COURSE_CREATED, course)

    def perform_update(self, serializer):
        user = self.request.user
        if user.role == User.Role.PLATFORM_ADMIN:
            serializer.save(content_owner=Course.ContentOwner.PLATFORM)
        else:
            serializer.validated_data.pop('organization', None)
            serializer.save(content_owner=Course.ContentOwner.ORGANIZATION)

    @action(detail=True, methods=['get', 'post'], url_path='access-grants')
    def access_grants(self, request, slug=None):
        """List (GET) or grant (POST) organization access to a PLATFORM-owned course."""
        course = self.get_object()

        if request.method == 'GET':
            grants = course.access_grants.select_related('organization')
            return Response(CourseAccessSerializer(grants, many=True).data)

        if course.content_owner != Course.ContentOwner.PLATFORM:
            raise ValidationError({'detail': 'Access grants only apply to platform-managed courses.'})

        organization = get_object_or_404(Organization, pk=request.data.get('organization'))
        grant, created = CourseAccess.objects.get_or_create(course=course, organization=organization)
        return Response(CourseAccessSerializer(grant).data, status=201 if created else 200)

    @action(detail=True, methods=['delete'], url_path='access-grants/revoke')
    def revoke_access(self, request, slug=None):
        course = self.get_object()
        deleted, _ = CourseAccess.objects.filter(course=course, organization_id=request.data.get('organization')).delete()
        if not deleted:
            return Response({'detail': 'No matching access grant.'}, status=404)
        return Response(status=204)

    @action(detail=True, methods=['post'], url_path='bulk-enroll')
    def bulk_enroll(self, request, slug=None):
        course = self.get_object()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'A CSV file is required (field name "file").'}, status=400)

        decoded = upload.read().decode('utf-8-sig', errors='ignore')
        emails = []
        for row in csv.reader(io.StringIO(decoded)):
            if not row:
                continue
            candidate = row[0].strip()
            if candidate and '@' in candidate:
                emails.append(candidate.lower())

        enrolled, already_enrolled, not_found = [], [], []
        for email in emails:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                not_found.append(email)
                continue
            _, created = Enrollment.objects.get_or_create(user=user, course=course)
            (enrolled if created else already_enrolled).append(email)

        return Response({
            'enrolled': enrolled,
            'already_enrolled': already_enrolled,
            'not_found': not_found,
        })

    @action(detail=True, methods=['post'])
    def invite(self, request, slug=None):
        """Enroll a single existing user by email — the one-off counterpart to bulk_enroll's CSV flow."""
        course = self.get_object()
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'detail': 'An email is required.'}, status=400)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({'detail': f'No account found for {email}.'}, status=404)

        _, created = Enrollment.objects.get_or_create(user=user, course=course)
        return Response({'email': email, 'created': created}, status=201 if created else 200)


class ModuleViewSet(viewsets.ModelViewSet):
    serializer_class = ModuleWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Module.objects.filter(course__in=editable_courses_for_user(self.request.user))

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        if not editable_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'course': 'You do not have permission to modify this course.'})
        serializer.save()

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Persist a drag-and-drop reorder of all modules within one course."""
        course_id = request.data.get('course')
        module_ids = request.data.get('module_ids')
        if not course_id or not isinstance(module_ids, list) or not module_ids:
            return Response({'detail': 'course and module_ids are required.'}, status=400)

        course = get_object_or_404(Course, pk=course_id)
        if not editable_courses_for_user(request.user).filter(pk=course.pk).exists():
            raise ValidationError({'course': 'You do not have permission to modify this course.'})

        existing_ids = set(Module.objects.filter(course=course).values_list('id', flat=True))
        if set(module_ids) != existing_ids or len(module_ids) != len(existing_ids):
            return Response({'detail': "module_ids must exactly match this course's modules."}, status=400)

        with transaction.atomic():
            for offset, module_id in enumerate(module_ids):
                Module.objects.filter(pk=module_id).update(order=REORDER_TEMP_OFFSET + offset)
            for index, module_id in enumerate(module_ids, start=1):
                Module.objects.filter(pk=module_id).update(order=index)

        modules = Module.objects.filter(course=course).order_by('order')
        return Response(ModuleOrderSerializer(modules, many=True).data)


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonWriteSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Lesson.objects.filter(module__course__in=editable_courses_for_user(self.request.user))

    def perform_create(self, serializer):
        module = serializer.validated_data['module']
        if not editable_courses_for_user(self.request.user).filter(pk=module.course_id).exists():
            raise ValidationError({'module': 'You do not have permission to modify this course.'})
        serializer.save()

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Persist a drag-and-drop reorder of all lessons within one module (no module change)."""
        module_id = request.data.get('module')
        lesson_ids = request.data.get('lesson_ids')
        if not module_id or not isinstance(lesson_ids, list) or not lesson_ids:
            return Response({'detail': 'module and lesson_ids are required.'}, status=400)

        module = get_object_or_404(Module, pk=module_id)
        if not editable_courses_for_user(request.user).filter(pk=module.course_id).exists():
            raise ValidationError({'module': 'You do not have permission to modify this module.'})

        existing_ids = set(Lesson.objects.filter(module=module).values_list('id', flat=True))
        if set(lesson_ids) != existing_ids or len(lesson_ids) != len(existing_ids):
            return Response({'detail': "lesson_ids must exactly match this module's lessons."}, status=400)

        with transaction.atomic():
            for offset, lesson_id in enumerate(lesson_ids):
                Lesson.objects.filter(pk=lesson_id).update(order=REORDER_TEMP_OFFSET + offset)
            for index, lesson_id in enumerate(lesson_ids, start=1):
                Lesson.objects.filter(pk=lesson_id).update(order=index)

        lessons = Lesson.objects.filter(module=module).order_by('order')
        return Response(LessonOrderSerializer(lessons, many=True).data)

    @action(detail=False, methods=['post'])
    def move(self, request):
        """
        Move a single lesson into a (possibly different) module at a specific
        position — persists a cross-module drag-and-drop. `lesson_ids` is the
        target module's full desired lesson id order, including the moved
        lesson; the source module's remaining lessons are compacted afterward
        to close the gap it left behind.
        """
        lesson_id = request.data.get('lesson')
        target_module_id = request.data.get('target_module')
        lesson_ids = request.data.get('lesson_ids')
        if not lesson_id or not target_module_id or not isinstance(lesson_ids, list) or not lesson_ids:
            return Response({'detail': 'lesson, target_module and lesson_ids are required.'}, status=400)

        lesson = get_object_or_404(Lesson, pk=lesson_id)
        target_module = get_object_or_404(Module, pk=target_module_id)
        source_module = lesson.module

        if not editable_courses_for_user(request.user).filter(pk=source_module.course_id).exists():
            raise ValidationError({'lesson': 'You do not have permission to modify this lesson.'})
        if not editable_courses_for_user(request.user).filter(pk=target_module.course_id).exists():
            raise ValidationError({'target_module': 'You do not have permission to modify this module.'})
        if source_module.course_id != target_module.course_id:
            raise ValidationError({'target_module': 'Cannot move a lesson to a module in a different course.'})

        expected_ids = set(
            Lesson.objects.filter(module=target_module).exclude(pk=lesson.id).values_list('id', flat=True)
        )
        expected_ids.add(lesson.id)
        if set(lesson_ids) != expected_ids or len(lesson_ids) != len(expected_ids):
            return Response(
                {'detail': "lesson_ids must exactly match the target module's lessons plus the moved lesson."},
                status=400,
            )

        with transaction.atomic():
            # Park the moved lesson in its new module at a sentinel well above the
            # temp-offset range used below, so it can't collide with the target
            # module's still-unrenumbered rows (or, transiently, with each other)
            # during the two-pass renumber that follows.
            Lesson.objects.filter(pk=lesson.id).update(module=target_module, order=REORDER_TEMP_OFFSET * 2)

            for offset, lid in enumerate(lesson_ids):
                Lesson.objects.filter(pk=lid).update(order=REORDER_TEMP_OFFSET + offset)
            for index, lid in enumerate(lesson_ids, start=1):
                Lesson.objects.filter(pk=lid).update(order=index)

            if source_module.id != target_module.id:
                remaining_ids = list(
                    Lesson.objects.filter(module=source_module).order_by('order').values_list('id', flat=True)
                )
                for offset, lid in enumerate(remaining_ids):
                    Lesson.objects.filter(pk=lid).update(order=REORDER_TEMP_OFFSET + offset)
                for index, lid in enumerate(remaining_ids, start=1):
                    Lesson.objects.filter(pk=lid).update(order=index)

        lessons = Lesson.objects.filter(
            module_id__in=[source_module.id, target_module.id]
        ).order_by('module_id', 'order')
        return Response(LessonOrderSerializer(lessons, many=True).data)


class SlideViewSet(viewsets.ModelViewSet):
    serializer_class = SlideSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Slide.objects.filter(lesson__module__course__in=editable_courses_for_user(self.request.user))

    def perform_create(self, serializer):
        lesson = serializer.validated_data['lesson']
        if not editable_courses_for_user(self.request.user).filter(pk=lesson.module.course_id).exists():
            raise ValidationError({'lesson': 'You do not have permission to modify this lesson.'})
        serializer.save()

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Persist a drag-and-drop reorder of all slides within one lesson."""
        lesson_id = request.data.get('lesson')
        slide_ids = request.data.get('slide_ids')
        if not lesson_id or not isinstance(slide_ids, list) or not slide_ids:
            return Response({'detail': 'lesson and slide_ids are required.'}, status=400)

        lesson = get_object_or_404(Lesson, pk=lesson_id)
        if not editable_courses_for_user(request.user).filter(pk=lesson.module.course_id).exists():
            raise ValidationError({'lesson': 'You do not have permission to modify this lesson.'})

        existing_ids = set(Slide.objects.filter(lesson=lesson).values_list('id', flat=True))
        if set(slide_ids) != existing_ids or len(slide_ids) != len(existing_ids):
            return Response({'detail': "slide_ids must exactly match this lesson's slides."}, status=400)

        with transaction.atomic():
            for offset, slide_id in enumerate(slide_ids):
                Slide.objects.filter(pk=slide_id).update(order=REORDER_TEMP_OFFSET + offset)
            for index, slide_id in enumerate(slide_ids, start=1):
                Slide.objects.filter(pk=slide_id).update(order=index)

        slides = Slide.objects.filter(lesson=lesson).order_by('order')
        return Response(SlideSummarySerializer(slides, many=True).data)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Copy a slide and all of its elements to the end of the same lesson."""
        slide = self.get_object()

        with transaction.atomic():
            new_slide = Slide.objects.create(
                lesson=slide.lesson,
                title=f'{slide.title} (copy)' if slide.title else '',
                order=Slide.objects.filter(lesson=slide.lesson).count() + 1,
                slide_type=slide.slide_type,
                layout=slide.layout,
                image_column_width=slide.image_column_width,
                template_override=slide.template_override,
                estimated_minutes=slide.estimated_minutes,
            )
            for element in slide.elements.order_by('order'):
                Element(
                    slide=new_slide,
                    order=element.order,
                    element_type=element.element_type,
                    rich_text=element.rich_text,
                    file=element.file,
                    video_url=element.video_url,
                    video_file=element.video_file,
                    embed_url=element.embed_url,
                    caption=element.caption,
                    align=element.align,
                ).save(edited_by=request.user)

        return Response(SlideSerializer(new_slide).data, status=201)


class ElementViewSet(viewsets.ModelViewSet):
    serializer_class = ElementSerializer

    def get_permissions(self):
        if self.action in WRITE_ACTIONS or self.action == 'reorder':
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        # Read actions (list/retrieve) are how the learner-facing player fetches
        # a CONTENT slide's elements, so they're scoped to visible (not just
        # editable) courses; writes stay editable-only via perform_create/etc.
        if self.action in WRITE_ACTIONS or self.action == 'reorder':
            courses = editable_courses_for_user(self.request.user)
        else:
            courses = visible_courses_for_user(self.request.user)
        queryset = Element.objects.filter(slide__lesson__module__course__in=courses)
        slide_id = self.request.query_params.get('slide')
        if slide_id:
            queryset = queryset.filter(slide_id=slide_id)
        return queryset

    def perform_create(self, serializer):
        slide = serializer.validated_data['slide']
        if not editable_courses_for_user(self.request.user).filter(pk=slide.lesson.module.course_id).exists():
            raise ValidationError({'slide': 'You do not have permission to modify this slide.'})
        serializer.save(edited_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(edited_by=self.request.user)

    def perform_destroy(self, instance):
        instance.delete(edited_by=self.request.user)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Persist a drag-and-drop reorder of all elements within one slide."""
        slide_id = request.data.get('slide')
        element_ids = request.data.get('element_ids')
        if not slide_id or not isinstance(element_ids, list) or not element_ids:
            return Response({'detail': 'slide and element_ids are required.'}, status=400)

        slide = get_object_or_404(Slide, pk=slide_id)
        if not editable_courses_for_user(request.user).filter(pk=slide.lesson.module.course_id).exists():
            raise ValidationError({'slide': 'You do not have permission to modify this slide.'})

        existing_ids = set(Element.objects.filter(slide=slide).values_list('id', flat=True))
        if set(element_ids) != existing_ids or len(element_ids) != len(existing_ids):
            return Response({'detail': "element_ids must exactly match this slide's elements."}, status=400)

        with transaction.atomic():
            for offset, element_id in enumerate(element_ids):
                Element.objects.filter(pk=element_id).update(order=REORDER_TEMP_OFFSET + offset)
            for index, element_id in enumerate(element_ids, start=1):
                Element.objects.filter(pk=element_id).update(order=index)

        # .update() above bypasses Element.save(), so the revision write that
        # would normally happen on a content change has to be triggered here.
        slide.write_revision(edited_by=request.user)

        elements = Element.objects.filter(slide=slide).order_by('order')
        return Response(ElementSerializer(elements, many=True).data)


class SlideTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """The curated set of slide background templates. Read-only — presets are
    managed via migration/admin, not the API — and visible to any
    authenticated user since learners need these colors to render slides too.
    """

    queryset = SlideTemplate.objects.all()
    serializer_class = SlideTemplateSerializer
    permission_classes = [IsAuthenticated]


class MediaUploadView(APIView):
    """
    Generic file upload for rich slide content (images, video, audio, file
    attachments). Saves through the same storage backend configured in
    STORAGES['default'] (core/settings.py — filesystem locally, S3 in
    production via USE_S3) that every other FileField/ImageField in this app
    already uses, rather than standing up a separate upload pipeline.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'A file is required (field name "file").'}, status=400)
        if upload.size > MAX_LESSON_FILE_SIZE_BYTES:
            return Response(
                {'detail': f'File size must not exceed {MAX_LESSON_FILE_SIZE_BYTES // (1024 * 1024)}MB.'},
                status=400,
            )

        extension = PurePosixPath(upload.name).suffix
        stored_name = f'slide_media/{uuid.uuid4().hex}{extension}'
        saved_path = default_storage.save(stored_name, upload)

        return Response(
            {
                'url': default_storage.url(saved_path),
                'name': upload.name,
                'size': upload.size,
                'content_type': upload.content_type or '',
            },
            status=201,
        )


class EnrollmentViewSet(RoleScopedQuerysetMixin, viewsets.ModelViewSet):
    # Deliberately just IsAuthenticated (no IsAdminRole): learners self-enroll and
    # mark their own slide progress; RoleScopedQuerysetMixin restricts which rows
    # are visible/editable, so no explicit role gate is needed on top of it.
    permission_classes = [IsAuthenticated]
    queryset = Enrollment.objects.select_related('user', 'course')
    serializer_class = EnrollmentSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    org_lookup = 'user__organization'
    owner_lookup = 'user'

    def get_queryset(self):
        queryset = super().get_queryset()
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        if not visible_courses_for_user(self.request.user).filter(pk=course.pk).exists():
            raise ValidationError({'course': 'This course is not available to you.'})
        enrollment = serializer.save()
        log_action(self.request.user, AuditLog.Action.ENROLLMENT_CREATED, enrollment)

    def perform_update(self, serializer):
        enrollment = serializer.save()
        log_action(self.request.user, AuditLog.Action.ENROLLMENT_UPDATED, enrollment)

    @action(detail=True, methods=['post'], url_path='complete-lesson')
    def complete_lesson(self, request, pk=None):
        enrollment = self.get_object()
        lesson = get_object_or_404(Lesson, pk=request.data.get('lesson'), module__course_id=enrollment.course_id)

        LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
            defaults={'completed_at': timezone.now()},
        )

        total_lessons = Lesson.objects.filter(module__course_id=enrollment.course_id).count()
        completed_lessons = enrollment.lesson_progress.count()
        enrollment.progress_percent = round((completed_lessons / total_lessons) * 100) if total_lessons else 0

        newly_completed = enrollment.progress_percent >= 100 and enrollment.status != Enrollment.Status.COMPLETED
        if enrollment.progress_percent >= 100:
            if enrollment.status != Enrollment.Status.COMPLETED:
                enrollment.completed_at = timezone.now()
            enrollment.status = Enrollment.Status.COMPLETED
        elif enrollment.status == Enrollment.Status.NOT_STARTED:
            enrollment.status = Enrollment.Status.IN_PROGRESS

        enrollment.save()
        if newly_completed:
            update_gamification_for_user(enrollment.user)
        log_action(request.user, AuditLog.Action.ENROLLMENT_UPDATED, enrollment)
        return Response(EnrollmentSerializer(enrollment).data)

    @action(detail=True, methods=['post'], url_path='slide-progress')
    def slide_progress(self, request, pk=None):
        """
        Records time spent on a Slide and, once the learner has satisfied its
        minimum dwell time (enforced client-side against Slide.estimated_minutes)
        and moved on, marks it complete — Slides are the unit of progress.
        """
        enrollment = self.get_object()
        slide = get_object_or_404(Slide, pk=request.data.get('slide'), lesson__module__course_id=enrollment.course_id)

        progress, created = SlideProgress.objects.get_or_create(
            enrollment=enrollment,
            slide=slide,
            defaults={'started_at': timezone.now()},
        )
        if not created and progress.started_at is None:
            progress.started_at = timezone.now()

        try:
            delta = int(request.data.get('time_spent_seconds', 0) or 0)
        except (TypeError, ValueError):
            delta = 0
        if delta > 0:
            progress.time_spent_seconds += delta

        if request.data.get('completed') and progress.completed_at is None:
            progress.completed_at = timezone.now()

        progress.save()

        total_slides = Slide.objects.filter(lesson__module__course_id=enrollment.course_id).count()
        completed_slides = enrollment.slide_progress.filter(completed_at__isnull=False).count()
        enrollment.progress_percent = round((completed_slides / total_slides) * 100) if total_slides else 0

        newly_completed = enrollment.progress_percent >= 100 and enrollment.status != Enrollment.Status.COMPLETED
        if enrollment.progress_percent >= 100:
            if enrollment.status != Enrollment.Status.COMPLETED:
                enrollment.completed_at = timezone.now()
            enrollment.status = Enrollment.Status.COMPLETED
        elif enrollment.status == Enrollment.Status.NOT_STARTED:
            enrollment.status = Enrollment.Status.IN_PROGRESS

        enrollment.save()
        if newly_completed:
            update_gamification_for_user(enrollment.user)
        log_action(request.user, AuditLog.Action.ENROLLMENT_UPDATED, enrollment)
        return Response(EnrollmentSerializer(enrollment).data)


class EnrollmentReportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        user = request.user
        queryset = Enrollment.objects.select_related('user', 'course')

        if user.role == User.Role.PLATFORM_ADMIN:
            pass
        elif user.role in (User.Role.ORG_ADMIN, User.Role.INSTRUCTOR):
            queryset = queryset.filter(user__organization_id=user.organization_id)

        course_id = request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(completed_at__date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(completed_at__date__lte=date_to)

        rows = []
        for enrollment in queryset.order_by('-enrolled_at'):
            best_score = QuizAttempt.objects.filter(
                user=enrollment.user, quiz__slide__lesson__module__course=enrollment.course
            ).aggregate(best=Max('score_percent'))['best']
            rows.append({
                'learner_email': enrollment.user.email,
                'learner_name': enrollment.user.get_full_name() or enrollment.user.email,
                'course_title': enrollment.course.title,
                'status': enrollment.status,
                'score_percent': float(best_score) if best_score is not None else None,
                'completion_date': enrollment.completed_at.isoformat() if enrollment.completed_at else None,
            })

        if request.query_params.get('export') == 'csv':
            return self._csv_response(rows)
        return Response(rows)

    def _csv_response(self, rows):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="enrollment_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Learner Email', 'Learner Name', 'Course', 'Status', 'Score %', 'Completion Date'])
        for row in rows:
            writer.writerow([
                _csv_safe(row['learner_email']),
                _csv_safe(row['learner_name']),
                _csv_safe(row['course_title']),
                row['status'],
                row['score_percent'] if row['score_percent'] is not None else '',
                row['completion_date'] or '',
            ])
        return response
