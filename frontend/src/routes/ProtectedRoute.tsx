import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { ForcedPasswordResetModal } from '../components/ForcedPasswordResetModal'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute() {
  const { user, isLoading, logout, refreshUser } = useAuth()
  const location = useLocation()
  const userId = user?.id
  const accessCheckKey = userId ? `${userId}:${location.pathname}` : ''
  const [verifiedAccessKey, setVerifiedAccessKey] = useState('')

  // Re-read the shared server-side status before mounting each protected
  // page. This catches a subscription or grace period expiring during an
  // already-open browser session, rather than waiting for a full reload.
  useEffect(() => {
    if (!userId || verifiedAccessKey === accessCheckKey) return
    let cancelled = false
    refreshUser()
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setVerifiedAccessKey(accessCheckKey)
      })
    return () => {
      cancelled = true
    }
  }, [accessCheckKey, refreshUser, userId, verifiedAccessKey])

  if (isLoading || (!!user && verifiedAccessKey !== accessCheckKey)) {
    return (
      <div className="flex min-h-screen items-center justify-center text-neutral-500">
        Loading…
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  // Subscription expiry deliberately comes before the forced-password flow:
  // login succeeded, but no post-login functionality should mount.
  if (user.subscription_access_locked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4">
        <div className="w-full max-w-lg rounded-xl border border-amber-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-xl font-semibold text-neutral-900">Your organization's subscription has expired</h1>
          <p className="mt-3 text-sm text-neutral-600">
            Contact your organization administrator or Siorik support to restore access.
          </p>
          <button type="button" onClick={logout} className="mt-6 text-sm font-medium text-brand-navy underline">
            Sign out
          </button>
        </div>
      </div>
    )
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
