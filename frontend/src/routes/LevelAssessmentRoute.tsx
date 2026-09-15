import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// /level-assessment is the learner's own exam-taking page, still reachable
// (and linked from the Dashboard's "My Level Assessment"/Pending cards) for
// LEARNER and PLATFORM_ADMIN. ORG_ADMIN/INSTRUCTOR no longer get a sidebar
// entry point for it and are redirected away from direct navigation too.
export function LevelAssessmentRoute() {
  const { user } = useAuth()

  if (user?.role === 'ORG_ADMIN' || user?.role === 'INSTRUCTOR') {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
