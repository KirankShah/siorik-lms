import { Outlet } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { useAuth } from '../context/AuthContext'
import { usePeriodicExamAvailability } from '../context/usePeriodicExamAvailability'

export function PeriodicExamRoute() {
  const { user } = useAuth()
  const { availability, isLoading } = usePeriodicExamAvailability()

  if (isLoading) return <p className="text-sm text-neutral-500">Checking Periodic Exam availability…</p>

  if (user?.role !== 'LEARNER' || !availability?.enabled) {
    return (
      <Card className="mx-auto max-w-xl text-center">
        <h1 className="text-xl font-semibold text-neutral-900">Periodic Exam is not available</h1>
        <p className="mt-2 text-sm text-neutral-600">
          There is no Periodic Exam available for your account or organisation right now.
        </p>
      </Card>
    )
  }

  return <Outlet />
}
