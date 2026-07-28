import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { isOrgSettingsRole } from '../lib/roles'

// Stricter than AdminRoute — excludes INSTRUCTOR. Organization Settings is an
// ORG_ADMIN/PLATFORM_ADMIN concern only.
export function OrgAdminRoute() {
  const { user } = useAuth()

  if (!user || !isOrgSettingsRole(user.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
