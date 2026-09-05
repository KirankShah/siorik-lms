import { apiFetch } from './apiClient'
import type { LevelAssessmentAttempt, MyAssessmentLevelStatus } from '../types/levelAssessments'

export function fetchMyAssessmentLevel(): Promise<MyAssessmentLevelStatus> {
  return apiFetch<MyAssessmentLevelStatus>('/my-assessment-level/')
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
