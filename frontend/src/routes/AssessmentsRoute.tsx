import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// AssessmentsPage (the read-only quiz inventory at /assessments) offers no
// capability ORG_ADMIN/INSTRUCTOR don't already have via course editing or
// Manage Assessment Questions — hidden from those two roles specifically.
// PLATFORM_ADMIN (and LEARNER, who already saw an empty read-only list here)
// are unaffected.
export function AssessmentsRoute() {
  const { user } = useAuth()

  if (user?.role === 'ORG_ADMIN' || user?.role === 'INSTRUCTOR') {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
