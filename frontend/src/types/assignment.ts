export type SubmissionType = 'FILE_UPLOAD' | 'TEXT'

export interface Assignment {
  id: number
  page: number
  instructions_json: unknown[]
  submission_type: SubmissionType
  max_marks: number
  due_offset_days: number | null
}

export interface AssignmentSubmissionUser {
  id: number
  email: string
  first_name: string
  last_name: string
}

export interface AssignmentSubmission {
  id: number
  assignment: number
  user: AssignmentSubmissionUser
  submitted_at: string
  file: string | null
  text_response: string
  marks_awarded: number | null
  grader_feedback: string
  graded_at: string | null
}
