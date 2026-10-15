import { apiFetch } from './apiClient'
import type {
  PeriodicExamAttempt,
  PeriodicExamAvailability,
  PeriodicExamLearnerSummary,
  PeriodicExamResult,
  PeriodicExamSettings,
  PeriodicExamSettingsUpdate,
  PlatformPeriodicExamOrganization,
} from '../types/periodicExams'

export function fetchPeriodicExamAvailability(): Promise<PeriodicExamAvailability> {
  return apiFetch('/periodic-exams/availability/')
}

export function fetchPeriodicExamSummary(): Promise<PeriodicExamLearnerSummary> {
  return apiFetch('/periodic-exams/me/summary/')
}

export function startPeriodicExamAttempt(): Promise<PeriodicExamAttempt> {
  return apiFetch('/periodic-exams/me/attempts/start/', { method: 'POST' })
}

export function fetchPeriodicExamAttempt(attemptId: number): Promise<PeriodicExamAttempt> {
  return apiFetch(`/periodic-exams/me/attempts/${attemptId}/`)
}

export function savePeriodicExamAnswer(
  attemptId: number,
  currentQuestionIndex: number,
  selectedOptionKeys: string[],
): Promise<PeriodicExamAttempt> {
  return apiFetch(`/periodic-exams/me/attempts/${attemptId}/current-answer/`, {
    method: 'PUT',
    body: { current_question_index: currentQuestionIndex, selected_option_keys: selectedOptionKeys },
  })
}

export function advancePeriodicExamAttempt(attemptId: number, currentQuestionIndex: number): Promise<PeriodicExamAttempt> {
  return apiFetch(`/periodic-exams/me/attempts/${attemptId}/advance/`, {
    method: 'POST',
    body: { current_question_index: currentQuestionIndex },
  })
}

export function submitPeriodicExamAttempt(attemptId: number): Promise<PeriodicExamAttempt> {
  return apiFetch(`/periodic-exams/me/attempts/${attemptId}/submit/`, { method: 'POST' })
}

export function fetchPeriodicExamResult(attemptId: number): Promise<PeriodicExamResult> {
  return apiFetch(`/periodic-exams/me/attempts/${attemptId}/result/`)
}

export function fetchPlatformPeriodicExamOrganizations(): Promise<PlatformPeriodicExamOrganization[]> {
  return apiFetch('/periodic-exams/platform/organizations/')
}

export function setPeriodicExamEnabled(organizationId: number, enabled: boolean) {
  return apiFetch<{ organization_id: number; enabled: boolean; enabled_from: string | null }>(
    `/periodic-exams/platform/organizations/${organizationId}/`,
    { method: 'PATCH', body: { enabled } },
  )
}

export function fetchPeriodicExamSettings(): Promise<PeriodicExamSettings> {
  return apiFetch('/periodic-exams/settings/')
}

export function updatePeriodicExamSettings(values: PeriodicExamSettingsUpdate): Promise<PeriodicExamSettings> {
  return apiFetch('/periodic-exams/settings/', { method: 'PATCH', body: values })
}
