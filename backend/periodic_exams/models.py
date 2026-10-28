from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


def default_reminder_days():
    return [7]


class PeriodicExamSettings(models.Model):
    class Frequency(models.TextChoices):
        MONTHLY = 'MONTHLY', 'Monthly'
        QUARTERLY = 'QUARTERLY', 'Quarterly'
        HALF_YEARLY = 'HALF_YEARLY', 'Half-yearly'
        YEARLY = 'YEARLY', 'Yearly'

    organization = models.OneToOneField(
        'accounts.Organization', on_delete=models.CASCADE, related_name='periodic_exam_settings'
    )
    enabled = models.BooleanField(default=False)
    frequency = models.CharField(max_length=20, choices=Frequency.choices, default=Frequency.MONTHLY)
    pending_frequency = models.CharField(max_length=20, choices=Frequency.choices, null=True, blank=True)
    pending_frequency_effective_at = models.DateTimeField(null=True, blank=True)
    questions_per_exam = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    pass_mark_percent = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    seconds_per_question = models.PositiveIntegerField(default=60, validators=[MinValueValidator(5)])
    max_attempts_per_cycle = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1)])
    reminders_enabled = models.BooleanField(default=True)
    reminder_days_before_end = models.JSONField(default=default_reminder_days)
    configuration_version = models.PositiveIntegerField(default=1)
    enabled_at = models.DateTimeField(null=True, blank=True)
    enabled_from = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_periodic_exam_settings',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'periodic exam settings'
        constraints = [
            models.CheckConstraint(check=Q(questions_per_exam__gte=1), name='pe_settings_questions_positive'),
            models.CheckConstraint(check=Q(pass_mark_percent__gte=0, pass_mark_percent__lte=100), name='pe_settings_pass_range'),
            models.CheckConstraint(check=Q(seconds_per_question__gte=5), name='pe_settings_seconds_min'),
            models.CheckConstraint(check=Q(max_attempts_per_cycle__gte=1), name='pe_settings_attempts_positive'),
        ]


class PeriodicExamCycle(models.Model):
    organization = models.ForeignKey(
        'accounts.Organization', on_delete=models.CASCADE, related_name='periodic_exam_cycles'
    )
    sequence = models.PositiveIntegerField()
    frequency_snapshot = models.CharField(max_length=20, choices=PeriodicExamSettings.Frequency.choices)
    configuration_version = models.PositiveIntegerField()
    questions_per_exam = models.PositiveIntegerField()
    pass_mark_percent = models.PositiveSmallIntegerField()
    seconds_per_question = models.PositiveIntegerField()
    max_attempts_per_cycle = models.PositiveSmallIntegerField()
    reminders_enabled = models.BooleanField()
    reminder_days_before_end = models.JSONField(default=default_reminder_days)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    start_date_ad = models.DateField()
    end_date_ad = models.DateField()
    start_year_bs = models.PositiveSmallIntegerField()
    start_month_bs = models.PositiveSmallIntegerField()
    start_day_bs = models.PositiveSmallIntegerField()
    end_year_bs = models.PositiveSmallIntegerField()
    end_month_bs = models.PositiveSmallIntegerField()
    end_day_bs = models.PositiveSmallIntegerField()
    fiscal_year_start_bs = models.PositiveSmallIntegerField()
    period_number = models.PositiveSmallIntegerField()
    display_label = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-starts_at']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'sequence'], name='pe_cycle_org_sequence_unique'),
            models.UniqueConstraint(fields=['organization', 'starts_at'], name='pe_cycle_org_start_unique'),
            models.CheckConstraint(check=Q(starts_at__lt=models.F('ends_at')), name='pe_cycle_dates_ordered'),
        ]
        indexes = [
            models.Index(fields=['organization', 'starts_at', 'ends_at'], name='pe_cycle_current_idx'),
            models.Index(fields=['organization', '-starts_at'], name='pe_cycle_recent_idx'),
        ]


class PeriodicExamCycleQuestion(models.Model):
    cycle = models.ForeignKey(
        PeriodicExamCycle, on_delete=models.CASCADE, related_name='question_pool'
    )
    level = models.CharField(max_length=30)
    source_question = models.ForeignKey(
        'levelassessments.LevelQuestion', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='periodic_exam_snapshots',
    )
    source_question_id_snapshot = models.PositiveBigIntegerField()
    normalized_text = models.TextField()
    normalized_text_hash = models.CharField(max_length=64)
    question_text = models.TextField()
    question_type = models.CharField(max_length=20)
    marks = models.PositiveIntegerField()
    choices = models.JSONField(default=list)
    correct_option_keys = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['level', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'level', 'normalized_text_hash'],
                name='pe_cycle_question_text_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['cycle', 'level'], name='pe_cycle_question_level_idx'),
        ]


class PeriodicExamParticipant(models.Model):
    cycle = models.ForeignKey(
        PeriodicExamCycle, on_delete=models.CASCADE, related_name='participants'
    )
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='periodic_exam_participations',
    )
    learner_id_snapshot = models.PositiveBigIntegerField()
    name_snapshot = models.CharField(max_length=301, blank=True)
    email_snapshot = models.EmailField()
    level_snapshot = models.CharField(max_length=30)
    branch_department_snapshot = models.CharField(max_length=150, blank=True)
    can_form_full_exam = models.BooleanField(default=True)
    attempts_used = models.PositiveSmallIntegerField(default=0)
    best_score_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    eligible_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['cycle', 'learner_id_snapshot']
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'learner_id_snapshot'], name='pe_participant_cycle_learner_unique'
            ),
        ]
        indexes = [
            models.Index(fields=['cycle', 'level_snapshot'], name='pe_participant_level_idx'),
            models.Index(fields=['cycle', 'passed_at', 'revoked_at'], name='pe_participant_status_idx'),
        ]


class PeriodicExamAttempt(models.Model):
    class SubmissionReason(models.TextChoices):
        LEARNER = 'LEARNER', 'Learner'
        QUESTION_TIMEOUT = 'QUESTION_TIMEOUT', 'Question timeout'

    participant = models.ForeignKey(
        PeriodicExamParticipant, on_delete=models.CASCADE, related_name='attempts'
    )
    attempt_number = models.PositiveSmallIntegerField()
    started_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    current_question_index = models.PositiveIntegerField(default=0)
    timer_segment_started_at = models.DateTimeField()
    score_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    passed = models.BooleanField(default=False)
    submission_reason = models.CharField(
        max_length=30, choices=SubmissionReason.choices, null=True, blank=True
    )

    class Meta:
        ordering = ['participant', 'attempt_number']
        constraints = [
            models.UniqueConstraint(
                fields=['participant', 'attempt_number'], name='pe_attempt_participant_number_unique'
            ),
        ]
        indexes = [
            models.Index(fields=['participant', 'submitted_at'], name='pe_attempt_open_idx'),
        ]


class PeriodicExamAttemptQuestion(models.Model):
    attempt = models.ForeignKey(
        PeriodicExamAttempt, on_delete=models.CASCADE, related_name='paper_questions'
    )
    cycle_question = models.ForeignKey(
        PeriodicExamCycleQuestion, on_delete=models.PROTECT, related_name='attempt_questions'
    )
    order = models.PositiveIntegerField()
    selected_option_keys = models.JSONField(default=list, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    marks_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['attempt', 'order'], name='pe_attempt_question_order_unique'),
            models.UniqueConstraint(
                fields=['attempt', 'cycle_question'], name='pe_attempt_question_unique'
            ),
        ]
        indexes = [
            models.Index(fields=['attempt', 'order'], name='pe_attempt_question_idx'),
        ]


class PeriodicExamQuestionUsage(models.Model):
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='periodic_exam_question_usage'
    )
    level = models.CharField(max_length=30)
    question_key = models.CharField(max_length=64)
    first_cycle_sequence = models.PositiveIntegerField()
    last_cycle_sequence = models.PositiveIntegerField()
    last_used_at = models.DateTimeField()
    times_used = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['learner', 'level', 'question_key'], name='pe_usage_learner_level_key_unique'
            ),
        ]
        indexes = [
            models.Index(
                fields=['learner', 'level', 'last_cycle_sequence', 'last_used_at'],
                name='pe_usage_lru_idx',
            ),
        ]


class PeriodicExamReminderDelivery(models.Model):
    cycle = models.ForeignKey(
        PeriodicExamCycle, on_delete=models.CASCADE, related_name='reminder_deliveries'
    )
    participant = models.ForeignKey(
        PeriodicExamParticipant, on_delete=models.CASCADE, related_name='reminder_deliveries'
    )
    days_before_end = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'participant', 'days_before_end'],
                name='pe_reminder_delivery_unique',
            ),
        ]
        indexes = [
            models.Index(fields=['cycle', 'days_before_end'], name='pe_reminder_cycle_due_idx'),
            models.Index(fields=['cycle', 'sent_at'], name='pe_reminder_unsent_idx'),
        ]
