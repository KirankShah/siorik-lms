from rest_framework import serializers

from accounts.serializers import OrganizationSerializer
from levelassessments.models import AssessmentLevel, LevelQuestion
from levelassessments.services import normalize_question_text

from .models import OrganizationSettings


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = OrganizationSettings
        fields = [
            'id', 'organization', 'questions_per_attempt', 'timing_mode', 'seconds_per_question',
            'total_exam_minutes', 'pass_mark_percent',
            'max_level_assessment_attempts', 'max_course_retake_attempts',
            'logged_in_inactive_reminder_enabled', 'logged_in_inactive_reminder_frequency',
            'logged_in_inactive_last_sent_at',
            'never_logged_in_reminder_enabled', 'never_logged_in_reminder_frequency', 'never_logged_in_last_sent_at',
        ]
        read_only_fields = [
            'id', 'organization', 'timing_mode', 'seconds_per_question',
            'logged_in_inactive_last_sent_at', 'never_logged_in_last_sent_at',
        ]

    def validate(self, attrs):
        """Keep the assessment duration and per-question countdown in sync.

        Org admins configure a question count and total duration; the server,
        rather than the browser, owns the calculation so API callers cannot
        save contradictory timing values. Existing unrelated PATCH requests
        also preserve a consistent pair of values.
        """
        attrs = super().validate(attrs)
        if self.instance is None:
            return attrs

        question_count = attrs.get('questions_per_attempt', self.instance.questions_per_attempt)
        total_minutes = attrs.get('total_exam_minutes', self.instance.total_exam_minutes)
        seconds_per_question = (total_minutes * 60) // question_count
        if seconds_per_question < 5:
            raise serializers.ValidationError({
                'total_exam_minutes': (
                    'The total duration must allow at least 5 seconds per question. '
                    'Increase the duration or reduce the number of questions.'
                ),
            })

        attrs['timing_mode'] = OrganizationSettings.TimingMode.PER_QUESTION
        attrs['seconds_per_question'] = seconds_per_question
        return attrs

    def validate_questions_per_attempt(self, value):
        """
        Warn at save time, not at attempt-start time: check `value` against
        the current question pool of every one of this organization's four
        AssessmentLevel tiers (see levelassessments.services.
        start_level_assessment_attempt, which would otherwise raise this same
        class of error only once a learner tries to start an attempt).

        Levels with an entirely empty pool (0 questions) are skipped here —
        that's "not set up yet", a separate concern from "the pool exists but
        is smaller than requested", and warning about it here would block an
        org admin from raising this number at all before they've imported
        questions for every one of the four levels, including ones they may
        never use.
        """
        organization = self.instance.organization if self.instance else None
        if organization is None:
            return value

        short_levels = []
        for level in AssessmentLevel.objects.filter(organization=organization):
            pool_rows = LevelQuestion.objects.filter(
                question_set__assessment_level=level
            ).values_list('id', 'question_text')
            unique_pool_size = len({
                normalize_question_text(question_text) or f'__question_{question_id}'
                for question_id, question_text in pool_rows
            })
            if 0 < unique_pool_size < value:
                short_levels.append((level.get_name_display(), unique_pool_size))

        if short_levels:
            details = '; '.join(f'{name} has only {count} unique' for name, count in short_levels)
            raise serializers.ValidationError(
                f'{value} questions per attempt is more than some levels\' unique question pools currently hold: '
                f'{details}. '
                'Import more questions for those levels first, or choose a smaller number.'
            )
        return value
