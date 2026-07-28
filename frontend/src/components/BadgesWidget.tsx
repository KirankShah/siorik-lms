import { Card } from './ui/Card'
import type { UserBadge } from '../types/gamification'

interface BadgesWidgetProps {
  badges: UserBadge[] | null
}

export function BadgesWidget({ badges }: BadgesWidgetProps) {
  return (
    <Card>
      <h2 className="text-sm font-semibold text-neutral-900">My Badges</h2>

      {!badges ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : badges.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">No badges yet — complete courses and quizzes to earn some.</p>
      ) : (
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
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
