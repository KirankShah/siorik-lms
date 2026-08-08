import { Link } from 'react-router-dom'
import { Card } from './ui/Card'
import type { UserBadge } from '../types/gamification'

interface BadgesWidgetProps {
  badges: UserBadge[] | null
}

export function BadgesWidget({ badges }: BadgesWidgetProps) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-neutral-900">My Achievements</h2>
        <Link to="/achievements" className="text-xs font-medium text-brand-navy hover:underline">
          View all Achievements
        </Link>
      </div>

      {!badges ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : badges.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">
          No achievements yet — complete courses and quizzes to earn some.
        </p>
      ) : (
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {badges.map((userBadge) => (
            <li
              key={userBadge.id}
              title={userBadge.badge.description}
              className="flex flex-col items-center gap-1 rounded-lg border border-neutral-200 p-3 text-center"
            >
              <span className="text-2xl">{userBadge.badge.icon}</span>
              <span className="text-xs font-medium text-neutral-700">{userBadge.badge.name}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
