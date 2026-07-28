import { apiFetch } from './apiClient'
import type { ScenarioAttempt, ScenarioChoice, ScenarioNode } from '../types/scenarios'

export function fetchScenarioNodesForSlide(slideId: number): Promise<ScenarioNode[]> {
  return apiFetch<ScenarioNode[]>(`/scenario-nodes/?slide=${slideId}`)
}

export interface ScenarioNodeInput {
  slide: number
  node_key: string
  prompt?: string
  prompt_image?: File | null
  is_start?: boolean
}

function buildScenarioNodeFormData(input: Partial<ScenarioNodeInput>): FormData {
  const formData = new FormData()
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined || value === null) continue
    formData.append(key, value instanceof File ? value : String(value))
  }
  return formData
}

export function createScenarioNode(input: ScenarioNodeInput): Promise<ScenarioNode> {
  const body = input.prompt_image instanceof File ? buildScenarioNodeFormData(input) : input
  return apiFetch<ScenarioNode>('/scenario-nodes/', { method: 'POST', body })
}

export function updateScenarioNode(id: number, input: Partial<ScenarioNodeInput>): Promise<ScenarioNode> {
  const body = input.prompt_image instanceof File ? buildScenarioNodeFormData(input) : input
  return apiFetch<ScenarioNode>(`/scenario-nodes/${id}/`, { method: 'PATCH', body })
}

export function deleteScenarioNode(id: number): Promise<void> {
  return apiFetch<void>(`/scenario-nodes/${id}/`, { method: 'DELETE' })
}

export interface ScenarioChoiceInput {
  node: number
  choice_text: string
  next_node?: number | null
  feedback_text?: string
  is_recommended?: boolean
  order?: number
}

export function createScenarioChoice(input: ScenarioChoiceInput): Promise<ScenarioChoice> {
  return apiFetch<ScenarioChoice>('/scenario-choices/', { method: 'POST', body: input })
}

export function updateScenarioChoice(id: number, input: Partial<ScenarioChoiceInput>): Promise<ScenarioChoice> {
  return apiFetch<ScenarioChoice>(`/scenario-choices/${id}/`, { method: 'PATCH', body: input })
}

export function deleteScenarioChoice(id: number): Promise<void> {
  return apiFetch<void>(`/scenario-choices/${id}/`, { method: 'DELETE' })
}

export function submitScenarioAttempt(input: { slide: number; path_taken: number[] }): Promise<ScenarioAttempt> {
  return apiFetch<ScenarioAttempt>('/scenario-attempts/', { method: 'POST', body: input })
}
