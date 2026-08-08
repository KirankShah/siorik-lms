import { Award, Crown, Medal, Trophy, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Card } from './ui/Card'
import { useAuth } from '../context/AuthContext'
import type { LeaderboardEntry } from '../types/gamification'

interface LeaderboardWidgetProps {
  entries: LeaderboardEntry[] | null
}

const TOP_RANKS_LIMIT = 5

const MEDAL_STYLES: Record<1 | 2 | 3, { bg: string; icon: string }> = {
  1: { bg: 'bg-brand-gold/15', icon: 'text-brand-gold' },
  2: { bg: 'bg-slate-200', icon: 'text-slate-500' },
  3: { bg: 'bg-amber-700/15', icon: 'text-amber-700' },
}

function initialsOf(entry: LeaderboardEntry): string {
  return `${entry.first_name?.[0] ?? ''}${entry.last_name?.[0] ?? ''}`.toUpperCase() || '?'
}

function Avatar({ entry, size = 'md' }: { entry: LeaderboardEntry; size?: 'sm' | 'md' }) {
  const dims = size === 'md' ? 'h-10 w-10 text-sm' : 'h-8 w-8 text-xs'
  return (
    <span
      className={`flex ${dims} shrink-0 items-center justify-center rounded-full bg-brand-navy/10 font-semibold text-brand-navy`}
    >
      {initialsOf(entry)}
    </span>
  )
}

interface StatPillProps {
  icon: LucideIcon
  iconBg: string
  iconColor: string
  valueColor: string
  value: number
  size?: 'sm' | 'md'
}

function StatPill({ icon: Icon, iconBg, iconColor, valueColor, value, size = 'md' }: StatPillProps) {
  const wrapDims = size === 'md' ? 'h-7 w-7' : 'h-6 w-6'
  const iconDims = size === 'md' ? 'h-4 w-4' : 'h-3.5 w-3.5'
  const textSize = size === 'md' ? 'text-base' : 'text-sm'

  return (
    <div className={`flex items-center gap-2 ${textSize} font-semibold ${valueColor}`}>
      <span className={`flex ${wrapDims} shrink-0 items-center justify-center rounded-full ${iconBg}`}>
        <Icon className={`${iconDims} ${iconColor}`} />
      </span>
      {value}
    </div>
  )
}

function RankBadge({ rank, size = 'md' }: { rank: number; size?: 'sm' | 'md' }) {
  const dims = size === 'md' ? 'h-9 w-9' : 'h-8 w-8'
  const iconSize = size === 'md' ? 'h-5 w-5' : 'h-4 w-4'

  if (rank === 1 || rank === 2 || rank === 3) {
    const medal = MEDAL_STYLES[rank]
    return (
      <span className={`flex ${dims} shrink-0 items-center justify-center rounded-full ${medal.bg}`}>
        <Medal className={`${iconSize} ${medal.icon}`} />
      </span>
    )
  }

  return (
    <span
      className={`flex ${dims} shrink-0 items-center justify-center rounded-full bg-neutral-200 text-sm font-semibold text-neutral-600`}
    >
      {rank}
    </span>
  )
}

export function LeaderboardWidget({ entries }: LeaderboardWidgetProps) {
  const { user } = useAuth()
  const myIndex = entries?.findIndex((entry) => entry.user_id === user?.id) ?? -1
  const myEntry = myIndex >= 0 ? (entries as LeaderboardEntry[])[myIndex] : null
  const myRank = myIndex + 1
  const topEntries = entries ? entries.slice(0, TOP_RANKS_LIMIT) : []

  return (
    <div className="space-y-4">
      <Card className="p-6 sm:p-8">
        <div className="flex items-center gap-2.5">
          <Trophy className="h-5 w-5 text-brand-gold" />
          <h2 className="text-lg font-semibold text-neutral-900">My Rank</h2>
        </div>

        {!entries ? (
          <p className="mt-4 text-sm text-neutral-500">Loading…</p>
        ) : !myEntry ? (
          <p className="mt-4 text-sm text-neutral-400">Complete a course or quiz to join the leaderboard.</p>
        ) : (
          <div className="mt-5 flex flex-wrap items-center gap-5 rounded-xl bg-brand-gold/10 p-5 ring-1 ring-brand-gold/60">
            <RankBadge rank={myRank} />
            <Avatar entry={myEntry} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-neutral-900">
                {myEntry.first_name} {myEntry.last_name}
              </p>
              <p className="text-xs text-neutral-500">
                Rank #{myRank} of {entries.length}
              </p>
            </div>
            <StatPill
              icon={Crown}
              iconBg="bg-brand-gold/15"
              iconColor="text-brand-gold"
              valueColor="text-brand-navy"
              value={myEntry.total_points}
            />
            <StatPill
              icon={Award}
              iconBg="bg-brand-navy/10"
              iconColor="text-brand-navy"
              valueColor="text-neutral-700"
              value={myEntry.certificates_earned_count}
            />
          </div>
        )}
      </Card>

      <Card className="p-6 sm:p-8">
        <div className="flex items-center gap-2.5">
          <Users className="h-5 w-5 text-brand-navy" />
          <h2 className="text-lg font-semibold text-neutral-900">Top Ranks</h2>
        </div>

        {!entries ? (
          <p className="mt-4 text-sm text-neutral-500">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="mt-4 text-sm text-neutral-500">No standings yet — complete a course to get on the board.</p>
        ) : (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full table-fixed border-collapse">
              <thead>
                <tr className="text-xs font-medium uppercase tracking-wide text-neutral-400">
                  <th className="pb-2 text-left font-medium">Users</th>
                  <th className="w-24 pb-2 text-right font-medium">Points</th>
                  <th className="w-28 pb-2 text-right font-medium">Certificates</th>
                </tr>
              </thead>
              <tbody>
                {topEntries.map((entry, index) => {
                  const rank = index + 1
                  const isMe = entry.user_id === user?.id
                  return (
                    <tr
                      key={entry.user_id}
                      className={`border-b border-neutral-100 transition-colors last:border-b-0 hover:bg-neutral-50 ${
                        isMe ? 'bg-brand-gold/10 hover:bg-brand-gold/15' : ''
                      }`}
                    >
                      <td className="py-3 pr-4">
                        <div className="flex min-w-0 items-center gap-3">
                          <RankBadge rank={rank} size="sm" />
                          <Avatar entry={entry} size="sm" />
                          <p className="truncate text-sm font-medium text-neutral-900">
                            {entry.first_name} {entry.last_name}
                            {isMe && <span className="ml-1 text-xs font-normal text-brand-navy">(You)</span>}
                          </p>
                        </div>
                      </td>
                      <td className="py-3">
                        <div className="flex justify-end">
                          <StatPill
                            icon={Crown}
                            iconBg="bg-brand-gold/15"
                            iconColor="text-brand-gold"
                            valueColor="text-brand-navy"
                            value={entry.total_points}
                            size="sm"
                          />
                        </div>
                      </td>
                      <td className="py-3">
                        <div className="flex justify-end">
                          <StatPill
                            icon={Award}
                            iconBg="bg-brand-navy/10"
                            iconColor="text-brand-navy"
                            valueColor="text-neutral-600"
                            value={entry.certificates_earned_count}
                            size="sm"
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
