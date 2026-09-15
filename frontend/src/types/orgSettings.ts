import type { Organization } from './auth'

export type ReminderFrequency = 'daily' | 'weekly' | 'fortnightly' | 'monthly'

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
  seconds_per_question: number
  pass_mark_percent: number
  logged_in_inactive_reminder_enabled: boolean
  logged_in_inactive_reminder_frequency: ReminderFrequency
  logged_in_inactive_last_sent_at: string | null
  never_logged_in_reminder_enabled: boolean
  never_logged_in_reminder_frequency: ReminderFrequency
  never_logged_in_last_sent_at: string | null
}

export type OrganizationSettingsInput = Partial<
  Pick<
    OrganizationSettings,
    | 'questions_per_attempt'
    | 'seconds_per_question'
    | 'pass_mark_percent'
    | 'logged_in_inactive_reminder_enabled'
    | 'logged_in_inactive_reminder_frequency'
    | 'never_logged_in_reminder_enabled'
    | 'never_logged_in_reminder_frequency'
  >
>
