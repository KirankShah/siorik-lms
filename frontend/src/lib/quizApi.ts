import { apiFetch } from './apiClient'
import type { QuestionType, QuizAnswerForGrading, QuizAttemptResult, QuizDetail } from '../types/quiz'

export function fetchQuizDetail(quizId: number): Promise<QuizDetail> {
  return apiFetch<QuizDetail>(`/quizzes/${quizId}/`)
}

// A Page of type QUIZ has at most one quiz in practice — null means none has
// been created yet (the authoring panel shows a "create quiz" empty state).
export async function fetchQuizForPage(pageId: number): Promise<QuizDetail | null> {
  const quizzes = await apiFetch<QuizDetail[]>(`/quizzes/?page=${pageId}`)
  return quizzes[0] ?? null
}

export interface QuizAnswerInput {
  question: number
  selected_choices: number[]
}

export function submitQuizAttempt(quizId: number, answers: QuizAnswerInput[]): Promise<QuizAttemptResult> {
  return apiFetch<QuizAttemptResult>(`/quizzes/${quizId}/submit/`, {
    method: 'POST',
    body: { answers },
  })
}

// --- Admin: quiz builder ---

export interface QuizInput {
  page: number
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
