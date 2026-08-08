import { Building2 } from 'lucide-react'
import { Card } from './ui/Card'
import type { User } from '../types/auth'

interface StatItem {
  label: string
  value: number | null
}

interface LearnerWelcomeBannerProps {
  user: User
  totalCourses: number | null
  completedCourses: number | null
  points: number | null
  badgesEarned: number | null
}

export function LearnerWelcomeBanner({ user, totalCourses, completedCourses, points, badgesEarned }: LearnerWelcomeBannerProps) {
  const initials = `${user.first_name?.[0] ?? ''}${user.last_name?.[0] ?? ''}`.toUpperCase() || '?'

  const stats: StatItem[] = [
    { label: 'Total Courses', value: totalCourses },
    { label: 'Completed', value: completedCourses },
    { label: 'Points Earned', value: points },
    { label: 'Achievements Earned', value: badgesEarned },
  ]

  return (
    <Card className="p-6 sm:p-8">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-brand-navy text-lg font-semibold text-white">
            {initials}
          </div>
          <div>
            <h1 className="text-xl font-semibold text-neutral-900">
              Welcome back{user.first_name ? `, ${user.first_name}` : ''}
            </h1>
            <p className="mt-1 text-xs font-medium text-neutral-500">Learner</p>
            {user.organization && (
              <span className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-brand-navy/10 px-2.5 py-1 text-xs font-medium text-brand-navy">
                <Building2 className="h-3 w-3" />
                {user.organization.name}
              </span>
            )}
          </div>
        </div>

        <div className="hidden h-16 w-px shrink-0 bg-neutral-200 sm:block" />

        <div className="grid flex-1 grid-cols-2 gap-y-4 sm:grid-cols-4 sm:divide-x sm:divide-neutral-200">
          {stats.map((stat) => (
            <div key={stat.label} className="flex flex-col items-center justify-center px-2 text-center sm:px-4">
              <p className="text-2xl font-bold text-neutral-900">{stat.value ?? '–'}</p>
              <p className="mt-1 text-xs text-neutral-500">{stat.label}</p>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
