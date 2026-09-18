import { Award, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { UserBadge } from '../types/gamification'
import { Button } from './ui/Button'
import { Modal } from './ui/Modal'

interface AchievementCelebrationModalProps {
  userBadge: UserBadge
  learnerName?: string
  remainingCount: number
  onAcknowledge: (userBadgeId: number) => Promise<void>
}

export function AchievementCelebrationModal({
  userBadge,
  learnerName,
  remainingCount,
  onAcknowledge,
}: AchievementCelebrationModalProps) {
  const [isAcknowledging, setIsAcknowledging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function acknowledge() {
    if (isAcknowledging) return
    setIsAcknowledging(true)
    setError(null)
    try {
      await onAcknowledge(userBadge.id)
    } catch {
      setError('We could not save this acknowledgement. Please try again.')
      setIsAcknowledging(false)
    }
  }

  const badge = userBadge.badge
  const greeting = learnerName ? `Well done, ${learnerName}.` : 'Well done.'

  return (
    <Modal
      title="Achievement unlocked"
      onClose={acknowledge}
      widthClassName="max-w-md"
      footer={
        <Button onClick={acknowledge} disabled={isAcknowledging} className="min-w-32">
          {isAcknowledging ? 'Saving…' : remainingCount > 1 ? 'Celebrate next' : 'Keep learning'}
        </Button>
      }
    >
      <div className="achievement-celebration text-center">
        <div className="mx-auto flex w-fit items-center gap-2 rounded-full bg-brand-navy/5 px-3 py-1 text-[11px] font-semibold tracking-[0.16em] text-brand-navy uppercase">
          <Sparkles className="h-3.5 w-3.5 text-brand-gold" aria-hidden="true" />
          New achievement
        </div>

        <div className="relative mx-auto mt-6 flex h-28 w-28 items-center justify-center rounded-full border border-brand-gold/50 bg-gradient-to-br from-white via-amber-50 to-brand-gold/25 shadow-[0_14px_35px_rgba(3,33,71,0.14)]">
          <div className="absolute inset-2 rounded-full border border-brand-navy/10" />
          <span className="relative text-5xl" role="img" aria-label={`${badge.name} badge`}>
            {badge.icon || '🏅'}
          </span>
          <span className="absolute -right-1 -bottom-1 flex h-9 w-9 items-center justify-center rounded-full border-4 border-white bg-brand-navy text-brand-gold shadow-md">
            <Award className="h-4 w-4" aria-hidden="true" />
          </span>
        </div>

        <p className="mt-6 text-sm font-medium text-brand-navy">{greeting}</p>
        <h3 className="mt-1 text-2xl font-semibold tracking-tight text-neutral-900">{badge.name}</h3>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-neutral-600">
          {badge.description || 'Your commitment to learning has earned you a new achievement.'}
        </p>

        <div className="mt-5 rounded-lg border border-brand-gold/40 bg-amber-50/70 px-4 py-3 text-left">
          <p className="text-sm leading-6 text-neutral-700">
            Your progress reflects the consistency and commitment of a trusted banking professional. Keep building your
            expertise—you are doing excellent work.
          </p>
        </div>

        {remainingCount > 1 && (
          <p className="mt-4 text-xs font-medium text-neutral-500">
            {remainingCount - 1} more achievement{remainingCount === 2 ? '' : 's'} waiting to be celebrated
          </p>
        )}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      </div>
    </Modal>
  )
}
