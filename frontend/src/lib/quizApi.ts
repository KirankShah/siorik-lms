import { apiFetch } from './apiClient'
import type {
  FillBlankMode,
  QuestionType,
  QuizAnswerForGrading,
  QuizAttemptResult,
  QuizDetail,
  QuizListItem,
} from '../types/quiz'

export function fetchQuizDetail(quizId: number): Promise<QuizDetail> {
  return apiFetch<QuizDetail>(`/quizzes/${quizId}/`)
}

// Unfiltered list — scoped server-side to quizzes in courses the caller can
// edit (empty for LEARNER, since editable_courses_for_user has nothing to
// give them).
export function fetchQuizzes(): Promise<QuizListItem[]> {
  return apiFetch<QuizListItem[]>('/quizzes/')
}

// A Slide of type QUIZ has at most one quiz in practice (not DB-enforced —
// Quiz.slide is a plain FK, not OneToOne) — null means none has been created
// yet (the authoring panel shows a "create quiz" empty state).
export async function fetchQuizForSlide(slideId: number): Promise<QuizDetail | null> {
  const quizzes = await apiFetch<QuizDetail[]>(`/quizzes/?slide=${slideId}`)
  return quizzes[0] ?? null
}

export interface QuizAnswerInput {
  question: number
  selected_choices: number[]
  // CATEGORIZE-only.
  category_placements?: { item: number; bucket: number }[]
  // HOTSPOT-only.
  selected_regions?: number[]
  // FILL_BLANK/TEXT_INPUT-only — {blank_index: typed text}.
  fill_blank_text?: Record<string, string>
  // FILL_BLANK/WORD_BANK-only.
  word_bank_placements?: { token: number; blank_index: number }[]
}

export function submitQuizAttempt(quizId: number, answers: QuizAnswerInput[]): Promise<QuizAttemptResult> {
  return apiFetch<QuizAttemptResult>(`/quizzes/${quizId}/submit/`, {
    method: 'POST',
    body: { answers },
  })
}

// --- Admin: quiz builder ---

export interface QuizInput {
  slide: number
  title: string
  pass_percentage: number
  time_limit_minutes: number | null
  max_attempts: number | null
  randomize_questions: boolean
}

export function createQuiz(input: QuizInput): Promise<{ id: number }> {
  return apiFetch('/quizzes/', { method: 'POST', body: input })
}

export function updateQuiz(id: number, input: Partial<QuizInput>): Promise<{ id: number }> {
  return apiFetch(`/quizzes/${id}/`, { method: 'PATCH', body: input })
}

export function deleteQuiz(id: number): Promise<void> {
  return apiFetch<void>(`/quizzes/${id}/`, { method: 'DELETE' })
}

export interface QuestionInput {
  quiz: number
  question_text: string
  question_type: QuestionType
  fill_blank_mode?: FillBlankMode
  order: number
  points: number
  image?: File | null
  video_url?: string
  explanation?: string
  marks?: number
  feedback_correct?: string
  feedback_incorrect?: string
}

function buildQuestionFormData(input: Partial<QuestionInput>): FormData {
  const formData = new FormData()
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined || value === null) continue
    formData.append(key, value instanceof File ? value : String(value))
  }
  return formData
}

export function createQuestion(input: QuestionInput): Promise<{ id: number }> {
  const body = input.image instanceof File ? buildQuestionFormData(input) : input
  return apiFetch('/questions/', { method: 'POST', body })
}

export function updateQuestion(id: number, input: Partial<QuestionInput>): Promise<{ id: number }> {
  const body = input.image instanceof File ? buildQuestionFormData(input) : input
  return apiFetch(`/questions/${id}/`, { method: 'PATCH', body })
}

export function deleteQuestion(id: number): Promise<void> {
  return apiFetch<void>(`/questions/${id}/`, { method: 'DELETE' })
}

export interface ChoiceInput {
  question: number
  choice_text: string
  is_correct?: boolean
  order?: number
  match_text?: string
  blank_index?: number | null
}

export function createChoice(input: ChoiceInput): Promise<{ id: number }> {
  return apiFetch('/choices/', { method: 'POST', body: input })
}

export function updateChoice(id: number, input: Partial<ChoiceInput>): Promise<{ id: number }> {
  return apiFetch(`/choices/${id}/`, { method: 'PATCH', body: input })
}

export function deleteChoice(id: number): Promise<void> {
  return apiFetch<void>(`/choices/${id}/`, { method: 'DELETE' })
}

export interface CategoryBucketInput {
  question: number
  label: string
  order?: number
}

export function createCategoryBucket(input: CategoryBucketInput): Promise<{ id: number }> {
  return apiFetch('/category-buckets/', { method: 'POST', body: input })
}

export function updateCategoryBucket(id: number, input: Partial<CategoryBucketInput>): Promise<{ id: number }> {
  return apiFetch(`/category-buckets/${id}/`, { method: 'PATCH', body: input })
}

export function deleteCategoryBucket(id: number): Promise<void> {
  return apiFetch<void>(`/category-buckets/${id}/`, { method: 'DELETE' })
}

export interface CategorizeItemInput {
  question: number
  item_text?: string
  item_image?: File | null
  correct_bucket: number
  order?: number
}

function buildCategorizeItemFormData(input: Partial<CategorizeItemInput>): FormData {
  const formData = new FormData()
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined || value === null) continue
    formData.append(key, value instanceof File ? value : String(value))
  }
  return formData
}

export function createCategorizeItem(input: CategorizeItemInput): Promise<{ id: number }> {
  const body = input.item_image instanceof File ? buildCategorizeItemFormData(input) : input
  return apiFetch('/categorize-items/', { method: 'POST', body })
}

export function updateCategorizeItem(id: number, input: Partial<CategorizeItemInput>): Promise<{ id: number }> {
  const body = input.item_image instanceof File ? buildCategorizeItemFormData(input) : input
  return apiFetch(`/categorize-items/${id}/`, { method: 'PATCH', body })
}

export function deleteCategorizeItem(id: number): Promise<void> {
  return apiFetch<void>(`/categorize-items/${id}/`, { method: 'DELETE' })
}

export interface HotspotRegionInput {
  question: number
  x: number
  y: number
  width: number
  height: number
  is_correct?: boolean
}

export function createHotspotRegion(input: HotspotRegionInput): Promise<{ id: number }> {
  return apiFetch('/hotspot-regions/', { method: 'POST', body: input })
}

export function updateHotspotRegion(id: number, input: Partial<HotspotRegionInput>): Promise<{ id: number }> {
  return apiFetch(`/hotspot-regions/${id}/`, { method: 'PATCH', body: input })
}

export function deleteHotspotRegion(id: number): Promise<void> {
  return apiFetch<void>(`/hotspot-regions/${id}/`, { method: 'DELETE' })
}

export interface WordBankTokenInput {
  question: number
  text: string
  correct_blank_index?: number | null
  order?: number
}

export function createWordBankToken(input: WordBankTokenInput): Promise<{ id: number }> {
  return apiFetch('/word-bank-tokens/', { method: 'POST', body: input })
}

export function updateWordBankToken(id: number, input: Partial<WordBankTokenInput>): Promise<{ id: number }> {
  return apiFetch(`/word-bank-tokens/${id}/`, { method: 'PATCH', body: input })
}

export function deleteWordBankToken(id: number): Promise<void> {
  return apiFetch<void>(`/word-bank-tokens/${id}/`, { method: 'DELETE' })
}

// --- Admin: grading ---

export function fetchUngradedQuizAnswers(): Promise<QuizAnswerForGrading[]> {
  return apiFetch<QuizAnswerForGrading[]>('/quiz-answers/?ungraded=true')
}

export function gradeQuizAnswer(
  id: number,
  input: { marks_awarded: number; grader_feedback: string },
): Promise<QuizAnswerForGrading> {
  return apiFetch<QuizAnswerForGrading>(`/quiz-answers/${id}/`, { method: 'PATCH', body: input })
}
