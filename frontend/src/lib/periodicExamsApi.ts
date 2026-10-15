import { apiFetch } from './apiClient'
import type {
  PeriodicExamSettings,
  PeriodicExamSettingsUpdate,
  PlatformPeriodicExamOrganization,
} from '../types/periodicExams'

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
