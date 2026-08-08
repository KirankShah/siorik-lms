import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { ForcedPasswordResetModal } from '../components/ForcedPasswordResetModal'
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
  // passes through, so no route ever mounts (no data fetches, nothing
  // interactive) until must_reset_password clears.
  if (user.must_reset_password) {
    return <ForcedPasswordResetModal />
  }

  return <Outlet />
}
