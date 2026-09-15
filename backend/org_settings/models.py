from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import Organization

PERCENT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class OrganizationSettings(models.Model):
    """
    One row per Organization — the single source of truth for the values
    that used to live scattered per-course (Course.certificate_pass_threshold)
    and per-AssessmentLevel (AssessmentLevel.pass_threshold/questions_per_attempt):
    course-completion certificate eligibility (certificates.services.
    certificate_ineligibility_reason) and every one of an organization's four
    level-assessment tiers (levelassessments.services.start_level_assessment_attempt,
    LevelAssessmentAttempt.calculate_score_percent) now read from here instead.
    Auto-created for every organization by the post_save signal in signals.py
    (existing orgs backfilled by migration 0002), so `organization.settings`
    is always available — no defensive DoesNotExist handling needed at call
    sites.

    Also carries the two configurable inactivity-reminder-email settings (see
    org_settings.services and the send_inactivity_reminders management
    command, run daily via a cPanel Cron Job — this host has no background
    task worker, so a scheduled command is the mechanism instead of Celery).
    """

    class ReminderFrequency(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        FORTNIGHTLY = 'fortnightly', 'Fortnightly'
        MONTHLY = 'monthly', 'Monthly'

    class TimingMode(models.TextChoices):
        # One countdown per question, resetting every time the learner
        # advances — the original behavior, and still the default.
        PER_QUESTION = 'PER_QUESTION', 'Per question'
        # A single countdown for the whole attempt, shown as one persistent
        # progress bar across every question — see LevelAssessmentPage.tsx.
        FIXED_TOTAL = 'FIXED_TOTAL', 'Fixed total for the exam'

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='settings')
    # Matches AssessmentLevel.questions_per_attempt's old default — see
    # levelassessments.services.start_level_assessment_attempt.
    questions_per_attempt = models.PositiveIntegerField(default=15, validators=[MinValueValidator(1)])
    timing_mode = models.CharField(max_length=20, choices=TimingMode.choices, default=TimingMode.PER_QUESTION)
    # Used only when timing_mode=PER_QUESTION — the sequential level-assessment
    # flow's per-question countdown; a question locks at zero marks once this
    # many seconds elapse unanswered.
    seconds_per_question = models.PositiveIntegerField(default=60, validators=[MinValueValidator(5)])
    # Used only when timing_mode=FIXED_TOTAL — one countdown for the entire
    # attempt; the exam auto-submits (unanswered questions scored zero) the
    # instant it reaches zero, wherever the learner currently is in the exam.
    total_exam_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(5)])
    # Matches AssessmentLevel.pass_threshold's old default — also now the
    # course-completion certificate threshold (Course.certificate_pass_threshold
    # used to hold this per-course; every course in an organization now shares
    # this single value, read from the enrolled learner's own organization).
    pass_mark_percent = models.PositiveIntegerField(default=70, validators=PERCENT_VALIDATORS)

    # Reminder for staff who HAVE logged in at least once but have zero
    # completed courses and zero level-assessment attempts — see
    # org_settings.services.logged_in_inactive_staff.
    logged_in_inactive_reminder_enabled = models.BooleanField(default=False)
    logged_in_inactive_reminder_frequency = models.CharField(
        max_length=20, choices=ReminderFrequency.choices, default=ReminderFrequency.WEEKLY,
    )
    # Per-ORGANIZATION, not per-user — the due-check (send_inactivity_reminders)
    # runs once per organization per command invocation, not once per recipient.
    logged_in_inactive_last_sent_at = models.DateTimeField(null=True, blank=True)

    # Reminder for staff who have NEVER logged in at all — see
    # org_settings.services.never_logged_in_staff. Independent on/off/frequency
    # from the reminder above; deliberately not merged into one control since
    # the two audiences (and appropriate messaging) are entirely different.
    never_logged_in_reminder_enabled = models.BooleanField(default=False)
    never_logged_in_reminder_frequency = models.CharField(
        max_length=20, choices=ReminderFrequency.choices, default=ReminderFrequency.WEEKLY,
    )
    never_logged_in_last_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.organization.name} settings'
