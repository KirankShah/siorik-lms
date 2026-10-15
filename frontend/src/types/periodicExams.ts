export type PeriodicExamFrequency = 'MONTHLY' | 'QUARTERLY' | 'HALF_YEARLY' | 'YEARLY'

export interface PeriodicExamQuestionCount {
  level: string
  level_display: string
  question_count: number
}

export interface PeriodicExamCycleSummary {
  id: number
  sequence: number
  frequency_snapshot: PeriodicExamFrequency
  display_label: string
  starts_at: string
  ends_at: string
  start_date_ad: string
  end_date_ad: string
  questions_per_exam: number
  pass_mark_percent: number
  seconds_per_question: number
  max_attempts_per_cycle: number
  reminders_enabled: boolean
  reminder_days_before_end: number[]
}

export interface PeriodicExamSettings {
  organization_id: number
  enabled: boolean
  frequency: PeriodicExamFrequency
  pending_frequency: PeriodicExamFrequency | null
  pending_frequency_effective_at: string | null
  questions_per_exam: number
  pass_mark_percent: number
  seconds_per_question: number
  max_attempts_per_cycle: number
  reminders_enabled: boolean
  reminder_days_before_end: number[]
  configuration_version: number
  enabled_from: string | null
  current_cycle: PeriodicExamCycleSummary | null
  question_counts: PeriodicExamQuestionCount[]
}

export interface PlatformPeriodicExamOrganization {
  id: number
  name: string
  slug: string
  is_active: boolean
  periodic_exam_enabled: boolean
  periodic_exam_enabled_from: string | null
  periodic_exam_question_counts: PeriodicExamQuestionCount[]
}

export type PeriodicExamSettingsUpdate = Pick<
  PeriodicExamSettings,
  | 'frequency'
  | 'questions_per_exam'
  | 'pass_mark_percent'
  | 'seconds_per_question'
  | 'max_attempts_per_cycle'
  | 'reminders_enabled'
  | 'reminder_days_before_end'
>
