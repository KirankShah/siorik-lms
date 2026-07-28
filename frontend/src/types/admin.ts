export interface ReportRow {
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
}
