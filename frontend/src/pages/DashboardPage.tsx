import { useAuth } from '../context/AuthContext'
import { Card } from '../components/ui/Card'

export function DashboardPage() {
  const { user } = useAuth()

  return (
    <Card>
      <h1 className="text-lg font-semibold text-neutral-900">Dashboard</h1>
      <p className="mt-2 text-sm text-neutral-600">
        Logged in as {user?.email}, role: {user?.role}
      </p>
    </Card>
  )
}
