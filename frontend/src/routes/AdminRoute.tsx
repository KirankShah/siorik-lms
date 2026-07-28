import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { isAdminRole } from '../lib/roles'

export function AdminRoute() {
  const { user } = useAuth()

  // ProtectedRoute (the parent route) already handles the unauthenticated/loading
  // cases, so by the time this renders `user` is guaranteed to be set.
  if (!user || !isAdminRole(user.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
