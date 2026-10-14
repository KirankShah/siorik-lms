import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NarrationPanel } from './NarrationPanel'
import { ApiError } from '../../lib/apiClient'
import { generateSlideNarration } from '../../lib/narrationApi'

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, role: 'PLATFORM_ADMIN' } }),
}))

vi.mock('../../lib/narrationApi', () => ({
  fetchNarrationsForSlide: vi.fn().mockResolvedValue([]),
  generateSlideNarration: vi.fn(),
}))

async function generateEnglishNarration() {
  render(<NarrationPanel slideId={800} />)
  const [englishButton] = await screen.findAllByRole('button', { name: 'Generate' })
  await userEvent.click(englishButton)
}

describe('NarrationPanel generation errors', () => {
  beforeEach(() => {
    vi.mocked(generateSlideNarration).mockReset()
  })

  it('shows a timeout when the host returns a non-JSON 504', async () => {
    vi.mocked(generateSlideNarration).mockRejectedValue(new ApiError(504, null))

    await generateEnglishNarration()

    expect(await screen.findByText('Server timed out (504). Please try again.')).toBeInTheDocument()
  })

  it('shows the HTTP status for any other non-JSON failure', async () => {
    vi.mocked(generateSlideNarration).mockRejectedValue(new ApiError(502, null))

    await generateEnglishNarration()

    expect(await screen.findByText('Narration generation failed. Please try again. (HTTP 502)')).toBeInTheDocument()
  })

  it('still shows the backend detail, including its reference, when the response is JSON', async () => {
    vi.mocked(generateSlideNarration).mockRejectedValue(
      new ApiError(400, {
        detail: 'The script was cut off. Try again or shorten the slide content. (Reference: ab12cd34)',
        reference: 'ab12cd34',
      }),
    )

    await generateEnglishNarration()

    expect(
      await screen.findByText('The script was cut off. Try again or shorten the slide content. (Reference: ab12cd34)'),
    ).toBeInTheDocument()
  })
})
