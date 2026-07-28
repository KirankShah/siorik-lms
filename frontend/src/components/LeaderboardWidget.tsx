import { Trophy } from 'lucide-react'
import { Card } from './ui/Card'
import { useAuth } from '../context/AuthContext'
import type { LeaderboardEntry } from '../types/gamification'

interface LeaderboardWidgetProps {
  entries: LeaderboardEntry[] | null
}

export function LeaderboardWidget({ entries }: LeaderboardWidgetProps) {
  const { user } = useAuth()
  const myIndex = entries?.findIndex((entry) => entry.user_id === user?.id) ?? -1

  return (
    <Card>
      <div className="flex items-center gap-2">
        <Trophy className="h-4 w-4 text-brand-gold" />
        <h2 className="text-sm font-semibold text-neutral-900">Leaderboard</h2>
      </div>

      {!entries ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">No standings yet — complete a course to get on the board.</p>
      ) : (
        <>
          <ol className="mt-4 space-y-2">
            {entries.slice(0, 5).map((entry, index) => {
              const isMe = entry.user_id === user?.id
              return (
                <li
                  key={entry.user_id}
                  className={`flex items-center gap-3 rounded-md px-3 py-2 ${
                    isMe ? 'bg-brand-gold/15 ring-1 ring-brand-gold' : 'bg-neutral-50'
                  }`}
                >
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                      index === 0 ? 'bg-brand-gold text-white' : 'bg-neutral-200 text-neutral-600'
                    }`}
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-neutral-900">
                      {entry.first_name} {entry.last_name}
                      {isMe && <span className="ml-1 text-xs font-normal text-brand-navy">(You)</span>}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {entry.courses_completed_count} {entry.courses_completed_count === 1 ? 'course' : 'courses'} · avg{' '}
                      {Math.round(Number(entry.average_quiz_score))}%
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-semibold text-brand-navy">{entry.total_points} pts</p>
                </li>
              )
            })}
          </ol>

          {myIndex >= 5 && (
            <p className="mt-3 text-xs text-neutral-500">
              You're currently ranked #{myIndex + 1} of {entries.length}.
            </p>
          )}
          {myIndex === -1 && (
            <p className="mt-3 text-xs text-neutral-400">Complete a course or quiz to join the leaderboard.</p>
          )}
        </>
      )}
    </Card>
  )
}
