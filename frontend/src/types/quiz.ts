export type QuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE' | 'TRUE_FALSE'

export interface Choice {
  id: number
  choice_text: string
  // Only present in the response when the current user's role is allowed to
  // see correct answers (INSTRUCTOR/ORG_ADMIN/PLATFORM_ADMIN) — absent for learners.
  is_correct?: boolean
}

export interface Question {
  id: number
  question_text: string
  question_type: QuestionType
  order: number
  points: number
  choices: Choice[]
}

export interface QuizSummary {
  id: number
  title: string
  pass_percentage: number
  time_limit_minutes: number | null
  max_attempts: number | null
}

export interface QuizDetail extends QuizSummary {
  course: number
  randomize_questions: boolean
  questions: Question[]
}

export interface QuizAnswerResult {
  id: number
  question: number
  selected_choices: number[]
  is_correct: boolean
}

export interface QuizAttemptResult {
  id: number
  user: number
  quiz: number
  started_at: string
  submitted_at: string | null
  score_percent: string
  passed: boolean
  attempt_number: number
  answers: QuizAnswerResult[]
}
