from rest_framework import serializers

from accounts.serializers import OrganizationSerializer
from levelassessments.models import AssessmentLevel, LevelQuestion

from .models import OrganizationSettings


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = OrganizationSettings
        fields = [
            'id', 'organization', 'questions_per_attempt', 'timing_mode', 'seconds_per_question',
            'total_exam_minutes', 'pass_mark_percent',
            'logged_in_inactive_reminder_enabled', 'logged_in_inactive_reminder_frequency',
            'logged_in_inactive_last_sent_at',
            'never_logged_in_reminder_enabled', 'never_logged_in_reminder_frequency', 'never_logged_in_last_sent_at',
        ]
        read_only_fields = [
            'id', 'organization', 'logged_in_inactive_last_sent_at', 'never_logged_in_last_sent_at',
        ]

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
            pool_size = LevelQuestion.objects.filter(question_set__assessment_level=level).count()
            if 0 < pool_size < value:
                short_levels.append((level.get_name_display(), pool_size))

        if short_levels:
            details = '; '.join(f'{name} has only {count}' for name, count in short_levels)
            raise serializers.ValidationError(
                f'{value} questions per attempt is more than some levels\' question pools currently hold: {details}. '
                'Import more questions for those levels first, or choose a smaller number.'
            )
        return value
