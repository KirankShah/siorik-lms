import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { isPlatformAdminRole } from '../lib/roles'

// Stricter than OrgAdminRoute — excludes ORG_ADMIN too. Creating a new
// organization is a platform-level (onboarding a new client) concern, not
// something an individual org's own admin does for themselves.
export function PlatformAdminRoute() {
  const { user } = useAuth()

  if (!user || !isPlatformAdminRole(user.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
