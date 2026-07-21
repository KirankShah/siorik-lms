import csv
import io

from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from assessments.models import QuizAttempt
from core.permissions import IsAdminRole, RoleScopedQuerysetMixin

from .models import Course, Enrollment, Lesson, LessonProgress, Module
from .permissions import editable_courses_for_user, visible_courses_for_user
from .serializers import (
    CourseDetailSerializer,
    CourseListSerializer,
    CourseWriteSerializer,
    EnrollmentSerializer,
    LessonWriteSerializer,
    ModuleWriteSerializer,
)

WRITE_ACTIONS = ('create', 'update', 'partial_update', 'destroy')


class CourseViewSet(viewsets.ModelViewSet):
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in WRITE_ACTIONS or self.action == 'bulk_enroll':
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
        if self.request.user.role == User.Role.PLATFORM_ADMIN:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user, organization=self.request.user.organization)

    def perform_update(self, serializer):
        if self.request.user.role != User.Role.PLATFORM_ADMIN:
            serializer.validated_data.pop('organization', None)
        serializer.save()

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


class EnrollmentViewSet(RoleScopedQuerysetMixin, viewsets.ModelViewSet):
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
        serializer.save()

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
                user=enrollment.user, quiz__course=enrollment.course
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
                row['learner_email'],
                row['learner_name'],
                row['course_title'],
                row['status'],
                row['score_percent'] if row['score_percent'] is not None else '',
                row['completion_date'] or '',
            ])
        return response
