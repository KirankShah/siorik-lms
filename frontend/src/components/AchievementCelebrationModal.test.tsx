import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AchievementCelebrationModal } from './AchievementCelebrationModal'
import type { UserBadge } from '../types/gamification'

const USER_BADGE: UserBadge = {
  id: 12,
  badge: {
    id: 3,
    key: 'first-strike',
    name: 'First Strike',
    description: 'Answered your first assessment question correctly.',
    icon: '⚡',
    unlock_condition: 'Answer one question correctly.',
  },
  earned_at: '2026-09-18T08:00:00Z',
  celebration_seen_at: null,
}

describe('AchievementCelebrationModal', () => {
  it('presents the earned badge with personalized, professional encouragement', () => {
    render(
      <AchievementCelebrationModal
        userBadge={USER_BADGE}
        learnerName="Lana"
        remainingCount={1}
        onAcknowledge={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog', { name: 'Achievement unlocked' })).toBeInTheDocument()
    expect(screen.getByText('Well done, Lana.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'First Strike' })).toBeInTheDocument()
    expect(screen.getByText(USER_BADGE.badge.description)).toBeInTheDocument()
    expect(screen.getByText(/trusted banking professional/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep learning' })).toBeInTheDocument()
  })

  it('acknowledges the badge before advancing', async () => {
    const onAcknowledge = vi.fn().mockResolvedValue(undefined)
    render(
      <AchievementCelebrationModal
        userBadge={USER_BADGE}
        remainingCount={2}
        onAcknowledge={onAcknowledge}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Celebrate next' }))

    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled()
    await waitFor(() => expect(onAcknowledge).toHaveBeenCalledWith(USER_BADGE.id))
    expect(screen.getByText(/1 more achievement waiting/i)).toBeInTheDocument()
  })

  it('keeps the celebration open and offers a retry when acknowledgement fails', async () => {
    const onAcknowledge = vi.fn().mockRejectedValue(new Error('network unavailable'))
    render(
      <AchievementCelebrationModal userBadge={USER_BADGE} remainingCount={1} onAcknowledge={onAcknowledge} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Keep learning' }))

    expect(await screen.findByText(/could not save this acknowledgement/i)).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Achievement unlocked' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep learning' })).toBeEnabled()
  })
})
