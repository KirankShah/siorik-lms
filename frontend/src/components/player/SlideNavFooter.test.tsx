import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SlideNavFooter } from './SlideNavFooter'

describe('SlideNavFooter Next-button tooltip', () => {
  it('shows a tooltip explaining why Next is disabled', () => {
    render(
      <SlideNavFooter
        hasPrevious={false}
        hasNext={true}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        nextDisabled={true}
        nextDisabledReason="Submit your answer to continue."
      />,
    )

    const nextButton = screen.getByRole('button', { name: /Next/ })
    expect(nextButton).toBeDisabled()
    expect(nextButton.closest('[title]')).toHaveAttribute('title', 'Submit your answer to continue.')
  })

  it('enables Next and shows no tooltip once no longer disabled', () => {
    render(
      <SlideNavFooter
        hasPrevious={false}
        hasNext={true}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        nextDisabled={false}
        nextDisabledReason="Submit your answer to continue."
      />,
    )

    const nextButton = screen.getByRole('button', { name: /Next/ })
    expect(nextButton).toBeEnabled()
    expect(nextButton.closest('[title]')).toBeNull()
  })
})
