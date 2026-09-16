import { apiFetch } from './apiClient'
import type { PaginatedResult } from './accountsApi'
import type {
  AssessmentLevelSummary,
  LevelAssessmentAttempt,
  LevelQuestionDetail,
  LevelQuestionEditInput,
  LevelQuestionImportResult,
  LevelQuestionListItem,
  LevelQuestionReplaceImpact,
  LevelQuestionUsage,
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
// rows are rejected — inspect `failed` on the result. `replace` scopes the
// import to a delete-then-recreate of only the Question Set labels present
// in the file (see previewReplaceLevelQuestions, which should be called
// first whenever `replace` is true so the admin can be warned of the impact
// before this destructive call runs).
export function importLevelQuestions(
  levelId: number,
  file: File,
  replace = false,
): Promise<LevelQuestionImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  if (replace) formData.append('replace', 'true')
  return apiFetch<LevelQuestionImportResult>(`/assessment-levels/${levelId}/import-questions/`, {
    method: 'POST',
    body: formData,
  })
}

// Dry run for a replace-import: reports which existing Question Set labels
// the file would touch and how many questions/learner answers a replace
// would delete, without changing anything. Call before importLevelQuestions
// with replace=true so the confirmation warning can name a specific count.
export function previewReplaceLevelQuestions(levelId: number, file: File): Promise<LevelQuestionReplaceImpact> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('replace', 'true')
  formData.append('dry_run', 'true')
  return apiFetch<LevelQuestionReplaceImpact>(`/assessment-levels/${levelId}/import-questions/`, {
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

// --- Question Bank admin ---

export interface LevelQuestionListFilters {
  organization?: number
  assessment_level?: string
  search?: string
  page?: number
  page_size?: number
}

// Admin-only, org-scoped server-side (see backend LevelQuestionAdminViewSet):
// an ORG_ADMIN/INSTRUCTOR always gets only their own organization regardless
// of `organization`, a PLATFORM_ADMIN gets every organization and must pass
// `organization` explicitly to narrow to one.
export function fetchLevelQuestions(filters: LevelQuestionListFilters = {}): Promise<PaginatedResult<LevelQuestionListItem>> {
  const params = new URLSearchParams()
  if (filters.organization) params.set('organization', String(filters.organization))
  if (filters.assessment_level) params.set('assessment_level', filters.assessment_level)
  if (filters.search) params.set('search', filters.search)
  if (filters.page) params.set('page', String(filters.page))
  if (filters.page_size) params.set('page_size', String(filters.page_size))
  const query = params.toString()
  return apiFetch<PaginatedResult<LevelQuestionListItem>>(`/level-questions/${query ? `?${query}` : ''}`)
}

export function fetchLevelQuestion(id: number): Promise<LevelQuestionDetail> {
  return apiFetch<LevelQuestionDetail>(`/level-questions/${id}/`)
}

// Validated server-side by the exact same rules as the Excel bulk import
// (see backend imports.py) — a 400 here carries the same kind of field
// errors a rejected import row would (e.g. correct_answers referencing an
// empty option).
export function updateLevelQuestion(id: number, input: LevelQuestionEditInput): Promise<LevelQuestionDetail> {
  return apiFetch<LevelQuestionDetail>(`/level-questions/${id}/`, { method: 'PATCH', body: input })
}

// Read-only — call before deleteLevelQuestion so the confirmation can name
// how many past attempts drew this question. Never blocks the delete
// itself, only informs it.
export function fetchLevelQuestionUsage(id: number): Promise<LevelQuestionUsage> {
  return apiFetch<LevelQuestionUsage>(`/level-questions/${id}/usage/`)
}

export function deleteLevelQuestion(id: number): Promise<void> {
  return apiFetch<void>(`/level-questions/${id}/`, { method: 'DELETE' })
}
