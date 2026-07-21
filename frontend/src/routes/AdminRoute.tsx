import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const ADMIN_ROLES = ['INSTRUCTOR', 'ORG_ADMIN', 'PLATFORM_ADMIN']

export function AdminRoute() {
  const { user } = useAuth()

  // ProtectedRoute (the parent route) already handles the unauthenticated/loading
  // cases, so by the time this renders `user` is guaranteed to be set.
  if (!user || !ADMIN_ROLES.includes(user.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
