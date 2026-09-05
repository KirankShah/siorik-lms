import type { Organization } from './auth'

export type LevelQuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_ANSWER'

export type LevelAssessmentStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'PASSED' | 'FAILED'

// Never carries is_correct — that's answer-key data, only ever revealed
// per-answer after submission (see LevelAssessmentAnswer below), same
// separation as backend LevelChoiceSerializer / assessments.Choice.
export interface LevelChoice {
  id: number
  choice_text: string
  order: number
}

export interface LevelQuestion {
  id: number
  question_text: string
  question_type: LevelQuestionType
  marks: number
  choices: LevelChoice[]
}

export interface AssessmentLevelSummary {
  id: number
  organization: Organization
  name: string
  name_display: string
  pass_threshold: number
  questions_per_attempt: number
}

export interface LevelAssessmentAnswer {
  id: number
  question: number
  selected_choices: number[]
  is_correct: boolean
  // Revealed only once this answer has been submitted and graded.
  correct_choice_ids: number[]
  explanation: string
  feedback_correct: string
  feedback_incorrect: string
}

export interface LevelAssessmentAttempt {
  id: number
  user: number
  assessment_level: number
  assessment_level_name: string
  pass_threshold: number
  started_at: string
  submitted_at: string | null
  score_percent: string
  passed: boolean
  questions: LevelQuestion[]
  answers: LevelAssessmentAnswer[]
}

export interface MyAssessmentLevelStatus {
  assigned: boolean
  assessment_level?: AssessmentLevelSummary
  status?: LevelAssessmentStatus
  open_attempt_id?: number | null
}
