export type QuestionType =
  | 'SINGLE_CHOICE'
  | 'MULTIPLE_CHOICE'
  | 'MULTIPLE_ANSWER'
  | 'TRUE_FALSE'
  | 'FILL_BLANK'
  | 'MATCHING'
  | 'ORDERING'
  | 'SHORT_ANSWER'
  | 'ESSAY'

// A single "answer option" row, reused across question types with different
// meaning per type — see backend assessments.models.Choice for the full
// breakdown. is_correct/match_text/order(on ORDERING questions) are all
// answer-key data and are stripped from the API response for learners.
export interface Choice {
  id: number
  choice_text: string
  is_correct?: boolean
  order: number
  match_text?: string
}

export interface Question {
  id: number
  question_text: string
  question_type: QuestionType
  order: number
  points: number
  image: string | null
  video_url: string | null
  // explanation/feedback_* are answer-key-adjacent and stripped for learners.
  explanation?: string
  marks: number
  feedback_correct?: string
  feedback_incorrect?: string
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
  page: number
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

// --- Grading ---

export interface GradingUser {
  id: number
  email: string
  first_name: string
  last_name: string
}

export interface GradingQuestion {
  id: number
  question_text: string
  question_type: QuestionType
  marks: number
}

export interface QuizAnswerForGrading {
  id: number
  question: GradingQuestion
  user: GradingUser
  quiz_title: string
  text_response: string
  marks_awarded: number | null
  grader_feedback: string
  graded_at: string | null
}
