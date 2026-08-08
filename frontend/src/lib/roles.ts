import type { Role } from '../types/auth'

export const ADMIN_ROLES: Role[] = ['INSTRUCTOR', 'ORG_ADMIN', 'PLATFORM_ADMIN']
export const ORG_SETTINGS_ROLES: Role[] = ['ORG_ADMIN', 'PLATFORM_ADMIN']
export const PLATFORM_ADMIN_ROLES: Role[] = ['PLATFORM_ADMIN']

export function isAdminRole(role: Role | null | undefined): boolean {
  return !!role && ADMIN_ROLES.includes(role)
}

export function isOrgSettingsRole(role: Role | null | undefined): boolean {
  return !!role && ORG_SETTINGS_ROLES.includes(role)
}

export function isPlatformAdminRole(role: Role | null | undefined): boolean {
  return !!role && PLATFORM_ADMIN_ROLES.includes(role)
}
