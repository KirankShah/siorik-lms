import type { Organization } from './auth'

export type ReminderFrequency = 'daily' | 'weekly' | 'fortnightly' | 'monthly'
export type TimingMode = 'PER_QUESTION' | 'FIXED_TOTAL'

// Mirrors org_settings.serializers.OrganizationSettingsSerializer. One row
// per organization (auto-created server-side, never created from here) —
// the single source of truth for the level-assessment question count/timer
// and the course-completion certificate pass mark, replacing what used to be
// AssessmentLevel.pass_threshold/questions_per_attempt (per level) and
// Course.certificate_pass_threshold (per course). Also carries the two
// independent inactivity-reminder-email configurations — see
// org_settings.services and the send_inactivity_reminders management command
// (run daily via cron; this host has no background task worker).
export interface OrganizationSettings {
  id: number
  organization: Organization
  questions_per_attempt: number
  timing_mode: TimingMode
  seconds_per_question: number
  total_exam_minutes: number
  pass_mark_percent: number
  // null = unlimited (the original behavior); a positive number is a hard
  // cap — see backend OrganizationSettings' own field docstring for exactly
  // what each counts.
  max_level_assessment_attempts: number | null
  max_course_retake_attempts: number | null
  // null keeps the limit authored on each quiz; a positive value overrides
  // every in-course quiz for learners in this organization.
  max_quiz_attempts: number | null
  // Platform-admin-only fields are omitted entirely from org-admin responses.
  max_active_learners?: number | null
  subscription_start_date?: string | null
  subscription_duration_days?: number | null
  org_admin_grace_period_days?: number
  subscription_expiry_date?: string | null
  org_admin_grace_expiry_date?: string | null
  logged_in_inactive_reminder_enabled: boolean
  logged_in_inactive_reminder_frequency: ReminderFrequency
  logged_in_inactive_last_sent_at: string | null
  never_logged_in_reminder_enabled: boolean
  never_logged_in_reminder_frequency: ReminderFrequency
  never_logged_in_last_sent_at: string | null
  path_overdue_reminder_enabled: boolean
  path_overdue_months_after_enrollment: number
  path_overdue_repeat_days: number
}

export type OrganizationSettingsInput = Partial<
  Pick<
    OrganizationSettings,
    | 'questions_per_attempt'
    | 'total_exam_minutes'
    | 'pass_mark_percent'
    | 'max_level_assessment_attempts'
    | 'max_course_retake_attempts'
    | 'max_quiz_attempts'
    | 'logged_in_inactive_reminder_enabled'
    | 'logged_in_inactive_reminder_frequency'
    | 'never_logged_in_reminder_enabled'
    | 'never_logged_in_reminder_frequency'
    | 'path_overdue_reminder_enabled'
    | 'path_overdue_months_after_enrollment'
    | 'path_overdue_repeat_days'
    | 'max_active_learners'
    | 'subscription_start_date'
    | 'subscription_duration_days'
    | 'org_admin_grace_period_days'
  >
>
