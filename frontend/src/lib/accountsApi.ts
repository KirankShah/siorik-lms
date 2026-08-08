import { apiFetch } from './apiClient'
import type { Organization, User } from '../types/auth'

export function fetchOrganizations(): Promise<Organization[]> {
  return apiFetch<Organization[]>('/organizations/')
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
