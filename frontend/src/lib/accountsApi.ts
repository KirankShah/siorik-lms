import { apiFetch } from './apiClient'
import type { Organization } from '../types/auth'

export function fetchOrganizations(): Promise<Organization[]> {
  return apiFetch<Organization[]>('/organizations/')
}
