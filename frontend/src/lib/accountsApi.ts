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

export interface StaffEnrollCreated {
  email: string
  assessment_level: string
}

export interface StaffEnrollFailure {
  row: number | null
  email: string
  reason: string
}

export interface StaffEnrollResult {
  created: StaffEnrollCreated[]
  failed: StaffEnrollFailure[]
}

// ORG_ADMIN/PLATFORM_ADMIN — bulk-creates real (non-demo) LEARNER accounts from
// the staff-enrollment spreadsheet (.xlsx or .csv). Each row's Assessment Level
// is stored on the account and drives which role-based assessment they see.
export function bulkEnrollStaff(file: File): Promise<StaffEnrollResult> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<StaffEnrollResult>('/staff/bulk/', { method: 'POST', body: formData })
}

// Individual counterpart to bulkEnrollStaff — same fields as one row of the
// spreadsheet, minus Organization (implicit: the caller's own org for
// ORG_ADMIN, explicit here only for PLATFORM_ADMIN, who administers more
// than one). Funnels through the exact same account-creation logic server-side.
export interface StaffCreateInput {
  name: string
  email: string
  assessment_level: string
  organization?: number
  corporate_title?: string
  functional_title?: string
  branch_department?: string
  phone_number?: string
}

export function createStaffMember(input: StaffCreateInput): Promise<User> {
  return apiFetch<User>('/staff/', { method: 'POST', body: input })
}

export interface StaffListFilters {
  search?: string
  status?: 'active' | 'inactive'
  organization?: number
  page?: number
  page_size?: number
}

export interface PaginatedResult<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export function fetchStaffList(filters: StaffListFilters = {}): Promise<PaginatedResult<User>> {
  const params = new URLSearchParams()
  if (filters.search) params.set('search', filters.search)
  if (filters.status) params.set('status', filters.status)
  if (filters.organization) params.set('organization', String(filters.organization))
  if (filters.page) params.set('page', String(filters.page))
  if (filters.page_size) params.set('page_size', String(filters.page_size))
  const query = params.toString()
  return apiFetch<PaginatedResult<User>>(`/staff/${query ? `?${query}` : ''}`)
}

// Revokes login access (sets is_active=False) without deleting the account or
// any of its related enrollments/certificates/attempts — see reactivateStaffMember.
export function deactivateStaffMember(userId: number): Promise<User> {
  return apiFetch<User>(`/staff/${userId}/deactivate/`, { method: 'POST' })
}

export function reactivateStaffMember(userId: number): Promise<User> {
  return apiFetch<User>(`/staff/${userId}/reactivate/`, { method: 'POST' })
}
