import { useEffect, useMemo, useState } from 'react'
import { Check, Lock, Search } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { ProgressBar } from '../components/ProgressBar'
import { fetchBadges, fetchMyBadges } from '../lib/gamificationApi'
import type { Badge, UserBadge } from '../types/gamification'

type LockFilter = 'ALL' | 'UNLOCKED' | 'LOCKED'

const FILTER_OPTIONS: { value: LockFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'UNLOCKED', label: 'Unlocked' },
  { value: 'LOCKED', label: 'Locked' },
]

interface AchievementCardProps {
  badge: Badge
  earnedAt: string | null
}

function AchievementCard({ badge, earnedAt }: AchievementCardProps) {
  const isEarned = earnedAt !== null

  return (
    <Card
      className={`flex flex-col items-center gap-3 p-6 text-center transition-transform duration-200 ${
        isEarned ? 'hover:scale-105' : ''
      }`}
    >
      <div
        className={`relative flex h-16 w-16 items-center justify-center rounded-full ${
          isEarned
            ? 'bg-gradient-to-br from-brand-gold/30 to-brand-gold/10 shadow-[0_0_24px_rgba(233,183,48,0.45)] ring-1 ring-brand-gold/40'
            : 'bg-neutral-100 ring-1 ring-neutral-200'
        }`}
      >
        <span className={`text-3xl ${isEarned ? '' : 'grayscale opacity-40'}`}>{badge.icon}</span>

        {isEarned ? (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-white">
            <Check className="h-3 w-3 text-white" strokeWidth={3} />
          </span>
        ) : (
          <span className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-neutral-400 ring-2 ring-white">
            <Lock className="h-3 w-3 text-white" />
          </span>
        )}
      </div>

      <div>
        <p className={`text-sm font-semibold ${isEarned ? 'text-neutral-900' : 'text-neutral-500'}`}>{badge.name}</p>
        <p className="mt-1 text-xs text-neutral-500">
          {isEarned ? badge.description : badge.unlock_condition || 'Keep learning to unlock this achievement.'}
        </p>
        {isEarned && (
          <p className="mt-1.5 text-[11px] font-medium text-brand-navy">
            Earned {new Date(earnedAt).toLocaleDateString()}
          </p>
        )}
      </div>
    </Card>
  )
}

export function AchievementsPage() {
  const [badges, setBadges] = useState<Badge[] | null>(null)
  const [myBadges, setMyBadges] = useState<UserBadge[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<LockFilter>('ALL')

  useEffect(() => {
    Promise.all([fetchBadges(), fetchMyBadges()])
      .then(([badgeList, userBadgeList]) => {
        setBadges(badgeList)
        setMyBadges(userBadgeList)
      })
      .catch(() => setError('Could not load achievements.'))
  }, [])

  const earnedAtByBadgeId = useMemo(() => {
    const map = new Map<number, string>()
    for (const userBadge of myBadges ?? []) {
      map.set(userBadge.badge.id, userBadge.earned_at)
    }
    return map
  }, [myBadges])

  const visibleAchievements = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (badges ?? [])
      .map((badge) => ({ badge, earnedAt: earnedAtByBadgeId.get(badge.id) ?? null }))
      .filter(({ badge }) => !query || badge.name.toLowerCase().includes(query))
      .filter(({ earnedAt }) => {
        if (filter === 'UNLOCKED') return earnedAt !== null
        if (filter === 'LOCKED') return earnedAt === null
        return true
      })
  }, [badges, earnedAtByBadgeId, search, filter])

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (!badges) {
    return <p className="text-sm text-neutral-500">Loading achievements…</p>
  }

  const totalCount = badges.length
  const unlockedCount = earnedAtByBadgeId.size

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Achievements</h1>

      <Card className="mt-4 p-4">
        <ProgressBar
          percent={totalCount ? Math.round((unlockedCount / totalCount) * 100) : 0}
          label={`${unlockedCount} of ${totalCount} Achievements Unlocked`}
        />
      </Card>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search Achievements"
            className="w-full rounded-md border border-neutral-300 py-1.5 pr-3 pl-9 text-sm placeholder:text-neutral-400 focus:border-brand-navy focus:outline-none"
          />
        </div>

        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as LockFilter)}
          className="rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
        >
          {FILTER_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {visibleAchievements.length === 0 ? (
        <Card className="mt-6 flex flex-col items-center gap-2 py-12 text-center">
          <p className="text-sm font-medium text-neutral-900">No achievements match</p>
          <p className="text-sm text-neutral-500">Try a different search or filter.</p>
        </Card>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {visibleAchievements.map(({ badge, earnedAt }) => (
            <AchievementCard key={badge.id} badge={badge} earnedAt={earnedAt} />
          ))}
        </div>
      )}
    </div>
  )
}
