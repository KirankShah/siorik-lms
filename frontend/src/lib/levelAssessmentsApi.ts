import { apiFetch } from './apiClient'
import type {
  AssessmentLevelSummary,
  LevelAssessmentAttempt,
  LevelQuestionImportResult,
  MyAssessmentLevelStatus,
} from '../types/levelAssessments'

export function fetchMyAssessmentLevel(): Promise<MyAssessmentLevelStatus> {
  return apiFetch<MyAssessmentLevelStatus>('/my-assessment-level/')
}

// Admin-only, read-only. Org-scoped server-side: an ORG_ADMIN/INSTRUCTOR only
// gets their own organization's levels, a PLATFORM_ADMIN gets every
// organization's. pass_threshold/questions_per_attempt/seconds_per_question
// are edited from the Organization Settings screen, not here — see
// lib/orgSettingsApi.ts.
export function fetchAssessmentLevels(): Promise<AssessmentLevelSummary[]> {
  return apiFetch<AssessmentLevelSummary[]>('/assessment-levels/')
}

// Admin-only bulk import of questions from a "Level Assessment Question
// Template" .xlsx workbook into one AssessmentLevel. Resolves even when some
// rows are rejected — inspect `failed` on the result.
export function importLevelQuestions(levelId: number, file: File): Promise<LevelQuestionImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<LevelQuestionImportResult>(`/assessment-levels/${levelId}/import-questions/`, {
    method: 'POST',
    body: formData,
  })
}

export function startLevelAssessmentAttempt(): Promise<LevelAssessmentAttempt> {
  return apiFetch<LevelAssessmentAttempt>('/level-attempts/start/', { method: 'POST' })
}

export function fetchLevelAssessmentAttempt(id: number): Promise<LevelAssessmentAttempt> {
  return apiFetch<LevelAssessmentAttempt>(`/level-attempts/${id}/`)
}

export interface LevelAssessmentAnswerInput {
  question: number
  selected_choices: number[]
}

export function submitLevelAssessmentAttempt(
  id: number,
  answers: LevelAssessmentAnswerInput[],
): Promise<LevelAssessmentAttempt> {
  return apiFetch<LevelAssessmentAttempt>(`/level-attempts/${id}/submit/`, {
    method: 'POST',
    body: { answers },
  })
}

// Persists the learner's current selection for one question into the
// attempt's resume scratch-pad — called on every answer change during a
// live attempt (not just when moving on), so a crash mid-selection still
// resumes with that selection intact. Never touches position or the timer.
export function saveLevelAssessmentAnswerProgress(
  attemptId: number,
  answer: LevelAssessmentAnswerInput,
): Promise<LevelAssessmentAttempt> {
  return apiFetch<LevelAssessmentAttempt>(`/level-attempts/${attemptId}/save-answer/`, {
    method: 'POST',
    body: answer,
  })
}

// Moves the attempt on to the next question — called right before the
// frontend locally advances (a Next/Finish click, or a PER_QUESTION timeout
// auto-advancing), so the server always knows exactly where the learner is
// and, under PER_QUESTION timing, resets the new question's own countdown.
export function advanceLevelAssessmentAttempt(
  attemptId: number,
  currentQuestionIndex: number,
): Promise<LevelAssessmentAttempt> {
  return apiFetch<LevelAssessmentAttempt>(`/level-attempts/${attemptId}/advance/`, {
    method: 'POST',
    body: { current_question_index: currentQuestionIndex },
  })
}
