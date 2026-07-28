export type QuestionType =
  | 'SINGLE_CHOICE'
  | 'MULTIPLE_CHOICE'
  | 'MULTIPLE_ANSWER'
  | 'TRUE_FALSE'
  | 'FILL_BLANK'
  | 'MATCHING'
  | 'ORDERING'
  | 'CATEGORIZE'
  | 'HOTSPOT'
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

// MATCHING's right-hand pool — one per Choice, `id` reused from the owning
// Choice (a correct drop is id === id), shuffled server-side for learners.
// Only present when question_type === 'MATCHING'.
export interface MatchTarget {
  id: number
  text: string
}

// CATEGORIZE's drop targets — always visible (only which item belongs in
// which bucket is secret).
export interface CategoryBucket {
  id: number
  label: string
  order: number
}

// CATEGORIZE's draggable items — correct_bucket is answer-key data and is
// stripped from the API response for learners, same treatment as
// Choice.is_correct.
export interface CategorizeItem {
  id: number
  item_text: string
  item_image: string | null
  correct_bucket?: number
  order: number
}

// HOTSPOT's clickable rectangles, drawn over Question.image. x/y/width/height
// are percentages (0-100) of the image's own dimensions, not pixels, so they
// still line up however large the image renders. is_correct is answer-key
// data and is stripped from the API response for learners.
export interface HotspotRegion {
  id: number
  x: number
  y: number
  width: number
  height: number
  is_correct?: boolean
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
  match_targets?: MatchTarget[] | null
  buckets: CategoryBucket[]
  categorize_items: CategorizeItem[]
  hotspot_regions: HotspotRegion[]
}

export interface QuizSummary {
  id: number
  title: string
  pass_percentage: number
  time_limit_minutes: number | null
  max_attempts: number | null
}

export interface QuizDetail extends QuizSummary {
  slide: number
  randomize_questions: boolean
  questions: Question[]
}

// Shape returned by GET /quizzes/ (list).
export interface QuizListItem {
  id: number
  slide: number
  title: string
  pass_percentage: number
  time_limit_minutes: number | null
  max_attempts: number | null
  randomize_questions: boolean
  questions: Question[]
}

export interface QuizAnswerResult {
  id: number
  question: number
  selected_choices: number[]
  // Only present for CATEGORIZE — the learner's submitted item id -> bucket
  // id placements. JSON object keys are always strings.
  category_placements: Record<string, number>
  // Only present for HOTSPOT — the learner's submitted region ids.
  selected_regions: number[]
  is_correct: boolean
  // Answer-key data revealed only for this specific answer, once an attempt
  // exists — see backend assessments.serializers.QuizAnswerSerializer.
  correct_choice_ids: number[]
  // Only present for ORDERING — the correct choice-id sequence.
  correct_order: number[] | null
  // Only present for CATEGORIZE — the correct item id -> bucket id mapping.
  correct_placements: Record<string, number> | null
  // Only present for HOTSPOT — the correct region ids.
  correct_region_ids: number[]
  explanation: string
  feedback_correct: string
  feedback_incorrect: string
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
