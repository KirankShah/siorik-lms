import { apiFetch } from './apiClient'
import type { QuestionType, QuizAttemptResult, QuizDetail } from '../types/quiz'

export function fetchQuizDetail(quizId: number): Promise<QuizDetail> {
  return apiFetch<QuizDetail>(`/quizzes/${quizId}/`)
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
  course: number
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
}

export function createQuestion(input: QuestionInput): Promise<{ id: number }> {
  return apiFetch('/questions/', { method: 'POST', body: input })
}

export function updateQuestion(id: number, input: Partial<QuestionInput>): Promise<{ id: number }> {
  return apiFetch(`/questions/${id}/`, { method: 'PATCH', body: input })
}

export function deleteQuestion(id: number): Promise<void> {
  return apiFetch<void>(`/questions/${id}/`, { method: 'DELETE' })
}

export interface ChoiceInput {
  question: number
  choice_text: string
  is_correct: boolean
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
