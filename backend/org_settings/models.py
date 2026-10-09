from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Organization

PERCENT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]
DEFAULT_PASS_MARK_PERCENT = 70


def pass_mark_percent_for_user(user):
    """Return the organization-wide pass mark that applies to ``user``."""
    if user.organization_id:
        return user.organization.settings.pass_mark_percent
    return DEFAULT_PASS_MARK_PERCENT


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
    # Derived from total_exam_minutes / questions_per_attempt by the org-admin
    # settings API. It remains stored because live attempts need one stable,
    # integer countdown value and older clients still read this field.
    seconds_per_question = models.PositiveIntegerField(default=60, validators=[MinValueValidator(5)])
    # Org admins choose the total intended duration. The per-question timer is
    # calculated as floor(total seconds / question count), so 30 minutes for
    # 30 questions produces exactly 60 seconds per question.
    total_exam_minutes = models.PositiveIntegerField(default=15, validators=[MinValueValidator(5)])
    # Matches AssessmentLevel.pass_threshold's old default — also now the
    # course-completion certificate threshold (Course.certificate_pass_threshold
    # used to hold this per-course; every course in an organization now shares
    # this single value, read from the enrolled learner's own organization).
    pass_mark_percent = models.PositiveIntegerField(default=DEFAULT_PASS_MARK_PERCENT, validators=PERCENT_VALIDATORS)

    # Null means unlimited (the original, still-default behavior) — a
    # positive number is a hard cap. max_level_assessment_attempts counts
    # every attempt (the first plus every retake) — see
    # levelassessments.services.start_level_assessment_attempt.
    # max_course_retake_attempts counts only the Retake Course action itself
    # (not the original attempt) — see courses.views.EnrollmentViewSet.retake
    # and Enrollment.retake_count. max_quiz_attempts is an optional
    # organization-wide override for every in-course quiz; when it is null,
    # the limit authored on each Quiz continues to apply.
    max_level_assessment_attempts = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    max_course_retake_attempts = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    max_quiz_attempts = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])

    # Platform-managed commercial controls. A null seat cap means unlimited.
    # A subscription is considered configured only when both start and
    # duration are present; its real expiry is start + duration days.
    max_active_learners = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    subscription_start_date = models.DateField(null=True, blank=True)
    subscription_duration_days = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    org_admin_grace_period_days = models.PositiveIntegerField(default=0)

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

    # Unlike the two organization-batch reminders above, path-overdue
    # reminders repeat on a per-learner schedule (the timestamp lives on
    # accounts.User), so these are only the shared eligibility settings.
    path_overdue_reminder_enabled = models.BooleanField(default=False)
    path_overdue_months_after_enrollment = models.PositiveIntegerField(
        default=2, validators=[MinValueValidator(1)]
    )
    path_overdue_repeat_days = models.PositiveIntegerField(default=7, validators=[MinValueValidator(1)])

    @property
    def subscription_expiry_date(self):
        if self.subscription_start_date is None or self.subscription_duration_days is None:
            return None
        return self.subscription_start_date + timedelta(days=self.subscription_duration_days)

    @property
    def org_admin_grace_expiry_date(self):
        expiry = self.subscription_expiry_date
        if expiry is None:
            return None
        return expiry + timedelta(days=self.org_admin_grace_period_days)

    def is_subscription_expired(self, on_date=None):
        expiry = self.subscription_expiry_date
        return expiry is not None and (on_date or timezone.localdate()) >= expiry

    def is_access_locked_for(self, user, on_date=None):
        """Subscription lock for tenant roles; platform admins are never affected."""
        if user.role == user.Role.PLATFORM_ADMIN or user.role not in (user.Role.ORG_ADMIN, user.Role.LEARNER):
            return False
        today = on_date or timezone.localdate()
        if not self.is_subscription_expired(today):
            return False
        if user.role == user.Role.ORG_ADMIN:
            grace_expiry = self.org_admin_grace_expiry_date
            return grace_expiry is None or today >= grace_expiry
        return True

    def __str__(self):
        return f'{self.organization.name} settings'
