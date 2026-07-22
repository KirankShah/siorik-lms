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

from .models import Course, CourseAccess, Enrollment, Lesson, LessonProgress, Module, Page, PageProgress
from .permissions import editable_courses_for_user, visible_courses_for_user
from .serializers import (
    CourseAccessSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
    CourseWriteSerializer,
    EnrollmentSerializer,
    LessonWriteSerializer,
    ModuleWriteSerializer,
    PageProgressSerializer,
    PageSerializer,
    PageSummarySerializer,
)
from .validators import MAX_LESSON_FILE_SIZE_BYTES

# Order values are bumped into this range as a first pass during a reorder,
# so that reassigning final 1..N values never collides with an order another
# page in the same lesson still holds — Page has a unique_together on
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
        if self.action in WRITE_ACTIONS or self.action == 'bulk_enroll' or self.action in self.ACCESS_GRANT_ACTIONS:
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


class PageViewSet(viewsets.ModelViewSet):
    serializer_class = PageSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        return Page.objects.filter(lesson__module__course__in=editable_courses_for_user(self.request.user))

    def perform_create(self, serializer):
        lesson = serializer.validated_data['lesson']
        if not editable_courses_for_user(self.request.user).filter(pk=lesson.module.course_id).exists():
            raise ValidationError({'lesson': 'You do not have permission to modify this lesson.'})
        serializer.save(edited_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(edited_by=self.request.user)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Persist a drag-and-drop reorder of all pages within one lesson."""
        lesson_id = request.data.get('lesson')
        page_ids = request.data.get('page_ids')
        if not lesson_id or not isinstance(page_ids, list) or not page_ids:
            return Response({'detail': 'lesson and page_ids are required.'}, status=400)

        lesson = get_object_or_404(Lesson, pk=lesson_id)
        if not editable_courses_for_user(request.user).filter(pk=lesson.module.course_id).exists():
            raise ValidationError({'lesson': 'You do not have permission to modify this lesson.'})

        existing_ids = set(Page.objects.filter(lesson=lesson).values_list('id', flat=True))
        if set(page_ids) != existing_ids or len(page_ids) != len(existing_ids):
            return Response({'detail': "page_ids must exactly match this lesson's pages."}, status=400)

        with transaction.atomic():
            for offset, page_id in enumerate(page_ids):
                Page.objects.filter(pk=page_id).update(order=REORDER_TEMP_OFFSET + offset)
            for index, page_id in enumerate(page_ids, start=1):
                Page.objects.filter(pk=page_id).update(order=index)

        pages = Page.objects.filter(lesson=lesson).order_by('order')
        return Response(PageSummarySerializer(pages, many=True).data)


class MediaUploadView(APIView):
    """
    Generic file upload for rich page content (BlockNote images, video, audio,
    file attachments). Saves through the same storage backend configured in
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
        stored_name = f'page_media/{uuid.uuid4().hex}{extension}'
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
    # mark their own lesson progress; RoleScopedQuerysetMixin restricts which rows
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

        if enrollment.progress_percent >= 100:
            if enrollment.status != Enrollment.Status.COMPLETED:
                enrollment.completed_at = timezone.now()
            enrollment.status = Enrollment.Status.COMPLETED
        elif enrollment.status == Enrollment.Status.NOT_STARTED:
            enrollment.status = Enrollment.Status.IN_PROGRESS

        enrollment.save()
        log_action(request.user, AuditLog.Action.ENROLLMENT_UPDATED, enrollment)
        return Response(EnrollmentSerializer(enrollment).data)

    @action(detail=True, methods=['post'], url_path='page-progress')
    def page_progress(self, request, pk=None):
        """
        Records time spent on a Page and, once the learner has satisfied its
        minimum dwell time (enforced client-side against Page.estimated_minutes)
        and moved on, marks it complete — replaces the old per-Lesson
        complete-lesson flow now that Pages are the unit of progress.
        """
        enrollment = self.get_object()
        page = get_object_or_404(Page, pk=request.data.get('page'), lesson__module__course_id=enrollment.course_id)

        progress, created = PageProgress.objects.get_or_create(
            enrollment=enrollment,
            page=page,
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

        total_pages = Page.objects.filter(lesson__module__course_id=enrollment.course_id).count()
        completed_pages = enrollment.page_progress.filter(completed_at__isnull=False).count()
        enrollment.progress_percent = round((completed_pages / total_pages) * 100) if total_pages else 0

        if enrollment.progress_percent >= 100:
            if enrollment.status != Enrollment.Status.COMPLETED:
                enrollment.completed_at = timezone.now()
            enrollment.status = Enrollment.Status.COMPLETED
        elif enrollment.status == Enrollment.Status.NOT_STARTED:
            enrollment.status = Enrollment.Status.IN_PROGRESS

        enrollment.save()
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
                user=enrollment.user, quiz__page__lesson__module__course=enrollment.course
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
