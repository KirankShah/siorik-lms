import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MatchingAnswer } from './MatchingAnswer'

describe('MatchingAnswer responsive layout', () => {
  it('constrains and wraps long pair text inside the quiz card', () => {
    const longItem = 'Increased scrutiny from international financial institutions '.repeat(5).trim()
    const longTarget = 'International banks apply more careful checks to transactions connected to Nepal '.repeat(5).trim()

    render(
      <MatchingAnswer
        items={[{ id: 1, text: longItem }]}
        targets={[{ id: 1, text: longTarget }]}
        assignments={{ 1: 1 }}
        onChange={vi.fn()}
      />,
    )

    const item = screen.getByRole('button', { name: longItem })
    const target = screen.getByText(longTarget)

    expect(item.className).toContain('min-w-0')
    expect(item.className).toContain('[overflow-wrap:anywhere]')
    expect(target.className).toContain('min-w-0')
    expect(target.className).toContain('[overflow-wrap:anywhere]')
    expect(target.parentElement?.className).toContain('grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]')
  })
})
