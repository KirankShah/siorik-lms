export type PeriodicExamFrequency = 'MONTHLY' | 'QUARTERLY' | 'HALF_YEARLY' | 'YEARLY'

export interface PeriodicExamQuestionCount {
  level: string
  level_display: string
  question_count: number
}

export interface PeriodicExamReadinessLevel {
  level: string
  level_display: string
  unique_question_count: number
  eligible_learner_count: number
  questions_per_exam: number
  can_form_full_exam: boolean
  note: string
}

export interface PeriodicExamReadiness {
  organization_id: number
  cycle_id: number | null
  as_of: string
  levels: PeriodicExamReadinessLevel[]
}

export interface PeriodicExamReportCycle {
  id: number
  display_label: string
  start_date_ad: string
  end_date_ad: string
}

export type PeriodicExamReportStatus = 'Passed' | 'Failed' | 'Retake required' | 'Not attempted' | 'In progress'

export interface PeriodicExamReportRow {
  staff_name: string
  email: string
  level: string
  branch_department: string
  cycle: string
  attempted: boolean
  completed: boolean
  attempts_used: number
  best_score: number | null
  status: PeriodicExamReportStatus
  last_attempt_date: string | null
  attempt_scores: Array<number | null>
}

export interface PeriodicExamReportPage {
  count: number
  page: number
  page_size: number
  results: PeriodicExamReportRow[]
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

export interface PeriodicExamAvailability {
  enabled: boolean
  available_from?: string | null
  current_cycle?: PeriodicExamCycleSummary | null
  /** Set only while the first cycle after enabling has not opened yet. */
  upcoming_cycle?: PeriodicExamUpcomingCycle | null
}

export interface PeriodicExamUpcomingCycle {
  starts_at: string
  start_date_ad: string
  display_label: string
}

export type PeriodicExamReasonCode =
  | 'ALREADY_PASSED'
  | 'REVOKED'
  | 'ATTEMPT_IN_PROGRESS'
  | 'ATTEMPT_LIMIT_REACHED'
  | 'INSUFFICIENT_POOL'
  | 'CYCLE_POOL_EXHAUSTED'
  | 'CYCLE_CLOSED'

export interface PeriodicExamLearnerSummary {
  cycle: Pick<PeriodicExamCycleSummary, 'id' | 'display_label' | 'starts_at' | 'ends_at' | 'questions_per_exam' | 'pass_mark_percent' | 'seconds_per_question' | 'max_attempts_per_cycle'>
  status: 'PENDING' | 'IN_PROGRESS' | 'RETAKE' | 'PASSED' | 'FAILED'
  attempted: boolean
  completed: boolean
  attempts_used: number
  attempts_remaining: number
  best_score_percent: string | null
  passed: boolean
  open_attempt_id: number | null
  last_completed_attempt_id: number | null
  can_start: boolean
  reason_code: PeriodicExamReasonCode | null
}

export interface PeriodicExamChoice {
  key: string
  text: string
}

export interface PeriodicExamQuestion {
  id: number
  question_text: string
  question_type: 'SINGLE_CHOICE' | 'MULTIPLE_ANSWER'
  marks: number
  choices: PeriodicExamChoice[]
  selected_option_keys: string[]
}

export interface PeriodicExamAttempt {
  id: number
  attempt_number: number
  submitted: boolean
  current_question_index: number
  total_questions: number
  remaining_seconds: number
  current_question?: PeriodicExamQuestion
  score_percent?: string
  passed?: boolean
}

export interface PeriodicExamResult {
  score_percent: string
  passed: boolean
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
>
