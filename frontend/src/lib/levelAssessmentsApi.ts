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

// Admin-only. Org-scoped server-side: an ORG_ADMIN/INSTRUCTOR only gets their
// own organization's levels, a PLATFORM_ADMIN gets every organization's.
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
