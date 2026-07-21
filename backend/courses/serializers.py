from django.utils import timezone
from rest_framework import serializers

from .models import Course, Enrollment, Lesson, Module


class LessonSerializer(serializers.ModelSerializer):
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
        ]


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'lessons']


class CourseListSerializer(serializers.ModelSerializer):
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
            'created_at',
        ]


class CourseDetailSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

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
            'created_by',
            'created_at',
            'updated_at',
            'modules',
        ]


class EnrollmentSerializer(serializers.ModelSerializer):
    completed_lesson_ids = serializers.SerializerMethodField()

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
        ]
        read_only_fields = ['id', 'user', 'enrolled_at', 'completed_at', 'completed_lesson_ids']

    def get_completed_lesson_ids(self, enrollment):
        return list(enrollment.lesson_progress.values_list('lesson_id', flat=True))

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
