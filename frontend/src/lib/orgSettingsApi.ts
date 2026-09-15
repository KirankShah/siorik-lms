import { apiFetch } from './apiClient'
import type { OrganizationSettings, OrganizationSettingsInput } from '../types/orgSettings'

// ORG_ADMIN/PLATFORM_ADMIN only (server-enforced — see
// org_settings.views.OrganizationSettingsViewSet). An ORG_ADMIN's list is
// always exactly their own organization's single row; a PLATFORM_ADMIN's is
// every organization's, one row each.
export function fetchOrganizationSettingsList(): Promise<OrganizationSettings[]> {
  return apiFetch<OrganizationSettings[]>('/organization-settings/')
}

export function updateOrganizationSettings(
  id: number,
  patch: OrganizationSettingsInput,
): Promise<OrganizationSettings> {
  return apiFetch<OrganizationSettings>(`/organization-settings/${id}/`, { method: 'PATCH', body: patch })
}
