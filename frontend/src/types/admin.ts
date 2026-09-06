export interface ReportRow {
  user_id: number
  learner_email: string
  learner_name: string
  course_title: string
  status: string
  score_percent: number | null
  completion_date: string | null
}

export interface BulkEnrollResult {
  enrolled: string[]
  already_enrolled: string[]
  not_found: string[]
  wrong_organization: string[]
}

export interface AnalyticsQuizAttempt {
  attempt_number: number
  score_percent: number
  passed: boolean
}

export interface AnalyticsQuiz {
  quiz_id: number
  quiz_title: string
  attempt_count: number
  best_score: number | null
  attempts: AnalyticsQuizAttempt[]
}

export type AnalyticsPassStatus = 'PASSED' | 'FAILED' | 'NOT_STARTED' | 'IN_PROGRESS'

export interface AnalyticsRow {
  organization_id: number | null
  organization_name: string
  user_id: number
  user_name: string
  user_email: string
  course_id: number
  course_title: string
  status: 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED'
  progress_percent: number
  // Same values as `status` while not yet COMPLETED — PASSED/FAILED only
  // apply once the enrollment is COMPLETED. See
  // backend certificates.services.certificate_ineligibility_reason.
  pass_status: AnalyticsPassStatus
  final_score: number | null
  time_spent_seconds: number
  total_quiz_attempts: number
  quizzes: AnalyticsQuiz[]
}

export interface AnalyticsOrganizationGroup {
  organization_id: number | null
  organization_name: string
  rows: AnalyticsRow[]
}
