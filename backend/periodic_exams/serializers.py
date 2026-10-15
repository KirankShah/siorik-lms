from rest_framework import serializers

from .models import PeriodicExamCycle, PeriodicExamSettings
from .services import update_operational_settings


class CycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodicExamCycle
        fields = [
            'id', 'sequence', 'frequency_snapshot', 'display_label', 'starts_at', 'ends_at',
            'start_date_ad', 'end_date_ad', 'start_year_bs', 'start_month_bs', 'start_day_bs',
            'end_year_bs', 'end_month_bs', 'end_day_bs',
            'questions_per_exam', 'pass_mark_percent', 'seconds_per_question',
            'max_attempts_per_cycle', 'reminders_enabled', 'reminder_days_before_end',
        ]


class PeriodicExamSettingsSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(read_only=True)
    current_cycle = serializers.SerializerMethodField()
    question_counts = serializers.SerializerMethodField()

    class Meta:
        model = PeriodicExamSettings
        fields = [
            'organization_id', 'enabled', 'frequency', 'pending_frequency',
            'pending_frequency_effective_at', 'questions_per_exam', 'pass_mark_percent',
            'seconds_per_question', 'max_attempts_per_cycle', 'reminders_enabled',
            'reminder_days_before_end', 'configuration_version', 'enabled_from', 'current_cycle',
            'question_counts',
        ]
        read_only_fields = [
            'enabled', 'pending_frequency', 'pending_frequency_effective_at',
            'configuration_version', 'enabled_from', 'current_cycle',
            'question_counts',
        ]

    def validate_reminder_days_before_end(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('Provide at least one reminder day.')
        if any(type(day) is not int or day < 1 or day > 366 for day in value):
            raise serializers.ValidationError('Reminder days must be unique integers from 1 to 366.')
        if len(set(value)) != len(value):
            raise serializers.ValidationError('Reminder days must be unique.')
        return sorted(value, reverse=True)

    def get_current_cycle(self, obj):
        cycle = getattr(obj, '_current_cycle', None)
        return CycleSerializer(cycle).data if cycle else None

    def get_question_counts(self, obj):
        return getattr(obj, '_question_counts', [])

    def update(self, instance, validated_data):
        return update_operational_settings(instance, validated_data, self.context['request'].user)


class PlatformOrganizationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    is_active = serializers.BooleanField()
    periodic_exam_enabled = serializers.BooleanField()
    periodic_exam_enabled_from = serializers.DateTimeField(allow_null=True)
    periodic_exam_question_counts = serializers.ListField(child=serializers.DictField())


class PlatformToggleSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


class ReadinessLevelSerializer(serializers.Serializer):
    level = serializers.CharField()
    level_display = serializers.CharField()
    unique_question_count = serializers.IntegerField()
    eligible_learner_count = serializers.IntegerField()
    questions_per_exam = serializers.IntegerField()
    can_form_full_exam = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True)


class ReadinessSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    cycle_id = serializers.IntegerField(allow_null=True)
    as_of = serializers.DateTimeField()
    levels = ReadinessLevelSerializer(many=True)
