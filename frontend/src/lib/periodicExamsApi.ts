import { apiFetch, apiFetchBlob } from './apiClient'
import type {
  PeriodicExamAttempt,
  PeriodicExamAvailability,
  PeriodicExamLearnerSummary,
  PeriodicExamResult,
  PeriodicExamReadiness,
  PeriodicExamReportCycle,
  PeriodicExamReportPage,
  PeriodicExamReportStatus,
  PeriodicExamSettings,
  PeriodicExamSettingsUpdate,
  PlatformPeriodicExamOrganization,
} from '../types/periodicExams'

export function fetchPeriodicExamAvailability(): Promise<PeriodicExamAvailability> {
  return apiFetch('/periodic-exams/availability/')
}

export function fetchPeriodicExamReadiness(organizationId?: number): Promise<PeriodicExamReadiness> {
  const query = organizationId ? `?organization_id=${organizationId}` : ''
  return apiFetch(`/periodic-exams/readiness/${query}`)
}

function reportQuery(organizationId?: number, values: Record<string, string | number | undefined> = {}) {
  const params = new URLSearchParams()
  if (organizationId) params.set('organization_id', String(organizationId))
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function fetchPeriodicExamReportCycles(organizationId?: number): Promise<PeriodicExamReportCycle[]> {
  return apiFetch(`/periodic-exams/report/cycles/${reportQuery(organizationId)}`)
}

export function fetchPeriodicExamReport(
  cycleId: number,
  options: { organizationId?: number; search?: string; status?: PeriodicExamReportStatus | ''; page?: number } = {},
): Promise<PeriodicExamReportPage> {
  const path = cycleId === 0 ? '/periodic-exams/report/history/' : `/periodic-exams/report/cycles/${cycleId}/`
  return apiFetch(`${path}${reportQuery(options.organizationId, {
    search: options.search, status: options.status, page: options.page,
  })}`)
}

async function downloadPeriodicExamReport(cycleId: number, format: 'csv' | 'xlsx', organizationId?: number) {
  const path = cycleId === 0
    ? `/periodic-exams/report/history.${format}`
    : `/periodic-exams/report/cycles/${cycleId}.${format}`
  const blob = await apiFetchBlob(
    `${path}${reportQuery(organizationId)}`,
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `periodic_exam_${cycleId === 0 ? 'history' : cycleId}.${format}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export const downloadPeriodicExamReportCsv = (cycleId: number, organizationId?: number) =>
  downloadPeriodicExamReport(cycleId, 'csv', organizationId)
export const downloadPeriodicExamReportXlsx = (cycleId: number, organizationId?: number) =>
  downloadPeriodicExamReport(cycleId, 'xlsx', organizationId)

export function fetchPeriodicExamSummary(cycleId?: number): Promise<PeriodicExamLearnerSummary> {
  return apiFetch(`/periodic-exams/me/summary/${cycleId ? `?cycle_id=${cycleId}` : ''}`)
}

export function fetchPeriodicExamHistory(): Promise<PeriodicExamLearnerSummary[]> {
  return apiFetch('/periodic-exams/me/history/')
}

export function startPeriodicExamAttempt(cycleId?: number): Promise<PeriodicExamAttempt> {
  return apiFetch(`/periodic-exams/me/attempts/start/${cycleId ? `?cycle_id=${cycleId}` : ''}`, { method: 'POST' })
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
