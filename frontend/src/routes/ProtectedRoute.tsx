import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-neutral-500">
        Loading…
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  // Any account created with a system-generated temp password (see the
  // "demo users" admin tool) must pick its own password before it can reach
  // anything else — this is the single choke point every protected route
  // passes through, so the redirect is enforced here rather than per-page.
  if (user.must_reset_password && location.pathname !== '/reset-password') {
    return <Navigate to="/reset-password" replace />
  }

  return <Outlet />
}
