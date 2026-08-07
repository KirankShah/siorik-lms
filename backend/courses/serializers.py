from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from accounts.serializers import OrganizationSerializer
from certificates.services import certificate_ineligibility_reason

from .models import (
    Course,
    CourseAccess,
    DemoLessonAccess,
    Element,
    Enrollment,
    Lesson,
    Module,
    Slide,
    SlideProgress,
    SlideTemplate,
)
from .permissions import is_lesson_locked_for_demo_user, visible_courses_for_user


class SlideTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlideTemplate
        fields = ['id', 'name', 'background_css', 'text_color', 'accent_color', 'order']


class SlideSummarySerializer(serializers.ModelSerializer):
    """Lightweight slide representation for nesting under a lesson, without its elements."""

    class Meta:
        model = Slide
        fields = [
            'id',
            'title',
            'order',
            'slide_type',
            'layout',
            'image_column_width',
            'template_override',
            'estimated_minutes',
        ]


class LessonSerializer(serializers.ModelSerializer):
    # Not a plain nested serializer field — get_slides below needs to check
    # is_locked first and return [] without touching the DB for the common
    # (non-demo-restricted) case.
    slides = serializers.SerializerMethodField()
    # True only for a demo user opening a lesson their course's
    # DemoLessonAccess grants don't cover — see is_lesson_locked_for_demo_user.
    # Always False for every other user, including on non-demo courses.
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id',
            'title',
            'lesson_type',
            'content_file',
            'content_url',
            'order',
            'estimated_minutes',
            'is_locked',
            'slides',
        ]

    def _is_locked(self, lesson):
        request = self.context.get('request')
        if request is None:
            return False
        return is_lesson_locked_for_demo_user(request.user, lesson)

    def get_is_locked(self, lesson):
        return self._is_locked(lesson)

    def get_slides(self, lesson):
        # A locked lesson's slides are withheld entirely, not just flagged —
        # this is what keeps them out of the frontend's flattened slide
        # sequence (lib/slideSequence.ts), so there's nothing to navigate to.
        # The actual content-fetch endpoints (ElementViewSet, QuizViewSet,
        # etc.) enforce the same lock independently — this is UI-shaping, not
        # the security boundary.
        if self._is_locked(lesson):
            return []
        slides = lesson.slides.order_by('order')
        return SlideSummarySerializer(slides, many=True, context=self.context).data


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'lessons']


class CourseListSerializer(serializers.ModelSerializer):
    # True only for a demo user (accounts.User.is_demo) viewing a course
    # outside their normal Organization assignment — see
    # courses.permissions.catalog_courses_for_user. Always False otherwise;
    # a locked course is still just a teaser card, since retrieving it
    # (and everything beneath it) stays gated by visible_courses_for_user.
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'description',
            'organization',
            'content_owner',
            'cover_image',
            'is_published',
            'template',
            'completion_deadline_days',
            'created_at',
            'updated_at',
            'is_locked',
        ]

    def get_is_locked(self, course):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_demo', False):
            return False
        assigned_ids = self.context.get('assigned_course_ids')
        if assigned_ids is not None:
            return course.pk not in assigned_ids
        return not visible_courses_for_user(user).filter(pk=course.pk).exists()


class CourseAccessSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = CourseAccess
        fields = ['id', 'organization', 'granted_at']


class CourseDetailSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)
    access_grants = CourseAccessSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'description',
            'organization',
            'content_owner',
            'cover_image',
            'is_published',
            'template',
            'certificate_pass_threshold',
            'certificate_expiry_months',
            'completion_deadline_days',
            'is_demo_available',
            'created_by',
            'created_at',
            'updated_at',
            'modules',
            'access_grants',
        ]


class CourseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'slug',
            'description',
            'organization',
            'content_owner',
            'cover_image',
            'is_published',
            'template',
            'certificate_pass_threshold',
            'certificate_expiry_months',
            'completion_deadline_days',
            'is_demo_available',
        ]


class DemoLessonAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoLessonAccess
        fields = ['id', 'course', 'lesson', 'created_at']
        read_only_fields = ['id', 'course', 'created_at']


class ModuleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'order']


class ModuleOrderSerializer(serializers.ModelSerializer):
    """Lightweight response for a module reorder — just the id/order pairs that changed."""

    class Meta:
        model = Module
        fields = ['id', 'order']


class LessonOrderSerializer(serializers.ModelSerializer):
    """Lightweight response for a lesson reorder/move — includes module so the frontend can reconcile cross-module moves."""

    class Meta:
        model = Lesson
        fields = ['id', 'order', 'module']


class LessonWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            'id',
            'module',
            'title',
            'lesson_type',
            'content_file',
            'content_url',
            'order',
            'estimated_minutes',
        ]

    def validate(self, attrs):
        # Lesson.clean() enforces file-extension-vs-lesson_type, but ModelSerializer
        # doesn't call it automatically — run it explicitly against a merged instance.
        instance = self.instance or Lesson()
        for field, value in attrs.items():
            setattr(instance, field, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        return attrs


class SlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slide
        fields = [
            'id',
            'lesson',
            'title',
            'order',
            'slide_type',
            'layout',
            'image_column_width',
            'template_override',
            'estimated_minutes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ElementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Element
        fields = [
            'id',
            'slide',
            'order',
            'element_type',
            'rich_text',
            'file',
            'video_url',
            'video_file',
            'embed_url',
            'caption',
            'align',
        ]

    # Element.save()/delete() write a SlideRevision snapshot on every change —
    # thread the requesting user through so it's attributed correctly.
    def create(self, validated_data):
        edited_by = validated_data.pop('edited_by', None)
        instance = Element(**validated_data)
        instance.save(edited_by=edited_by)
        return instance

    def update(self, instance, validated_data):
        edited_by = validated_data.pop('edited_by', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(edited_by=edited_by)
        return instance


class SlideProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlideProgress
        fields = ['id', 'slide', 'started_at', 'completed_at', 'time_spent_seconds']


class EnrollmentSerializer(serializers.ModelSerializer):
    completed_lesson_ids = serializers.SerializerMethodField()
    slide_progress = SlideProgressSerializer(many=True, read_only=True)
    # Null once the enrollment isn't COMPLETED yet, or once the learner is
    # actually eligible for a certificate. Otherwise the human-readable
    # reason they aren't (yet) — currently always the course-wide average
    # falling short of Course.certificate_pass_threshold, once every slide is
    # done. Read-only and side-effect-free; see
    # certificates.services.certificate_ineligibility_reason. Drives the
    # frontend's "Retake Course" action.
    certificate_ineligible_reason = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'id',
            'user',
            'course',
            'enrolled_at',
            'completed_at',
            'status',
            'progress_percent',
            'completed_lesson_ids',
            'slide_progress',
            'certificate_ineligible_reason',
        ]
        read_only_fields = [
            'id', 'user', 'enrolled_at', 'completed_at', 'completed_lesson_ids', 'slide_progress',
            'certificate_ineligible_reason',
        ]

    def get_completed_lesson_ids(self, enrollment):
        return list(enrollment.lesson_progress.values_list('lesson_id', flat=True))

    def get_certificate_ineligible_reason(self, enrollment):
        if enrollment.status != Enrollment.Status.COMPLETED:
            return None
        return certificate_ineligibility_reason(enrollment.user, enrollment.course)

    def validate_course(self, course):
        request = self.context['request']
        if Enrollment.objects.filter(user=request.user, course=course).exists():
            raise serializers.ValidationError('You are already enrolled in this course.')
        return course

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('course', None)
        new_status = validated_data.get('status')
        if new_status == Enrollment.Status.COMPLETED and instance.status != Enrollment.Status.COMPLETED:
            validated_data['completed_at'] = timezone.now()
            validated_data.setdefault('progress_percent', 100)
        return super().update(instance, validated_data)
