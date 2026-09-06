import { apiFetch } from './apiClient'
import type { Organization, User } from '../types/auth'

export function fetchOrganizations(): Promise<Organization[]> {
  return apiFetch<Organization[]>('/organizations/')
}

export interface OrganizationCreateInput {
  name: string
}

export function createOrganization(input: OrganizationCreateInput): Promise<Organization> {
  return apiFetch<Organization>('/organizations/', { method: 'POST', body: input })
}

export function deleteOrganization(id: number): Promise<void> {
  return apiFetch<void>(`/organizations/${id}/`, { method: 'DELETE' })
}

// PLATFORM_ADMIN-only — permanently deletes a LEARNER account (and,
// via cascade, their enrollments/attempts/submissions).
export function deleteLearner(userId: number): Promise<void> {
  return apiFetch<void>(`/learners/${userId}/`, { method: 'DELETE' })
}

export interface DemoUserInput {
  name: string
  email: string
  organization: number
  designation?: string
  phone_number?: string
}

export interface DemoUserBulkFailure {
  row: number
  email: string
  reason: string
}

export interface DemoUserBulkResult {
  created: string[]
  failed: DemoUserBulkFailure[]
}

export function createDemoUser(input: DemoUserInput): Promise<User> {
  return apiFetch<User>('/demo-users/', { method: 'POST', body: input })
}

export function bulkCreateDemoUsers(file: File): Promise<DemoUserBulkResult> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<DemoUserBulkResult>('/demo-users/bulk/', { method: 'POST', body: formData })
}

// PLATFORM_ADMIN-only — creates a real (non-demo) ORG_ADMIN account for the
// given organization. Same input shape as DemoUserInput, but a distinct
// endpoint: /demo-users/ always creates LEARNER/is_demo accounts.
export function createOrgAdmin(input: DemoUserInput): Promise<User> {
  return apiFetch<User>('/org-admins/', { method: 'POST', body: input })
}
