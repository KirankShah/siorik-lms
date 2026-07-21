import { useAuth } from '../context/AuthContext'

export function DashboardPage() {
  const { user } = useAuth()

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-lg font-semibold text-slate-900">Dashboard</h1>
      <p className="mt-2 text-sm text-slate-600">
        Logged in as {user?.email}, role: {user?.role}
      </p>
    </div>
  )
}
