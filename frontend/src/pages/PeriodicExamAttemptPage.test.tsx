import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PeriodicExamAttemptPage } from './PeriodicExamAttemptPage'
import {
  advancePeriodicExamAttempt,
  fetchPeriodicExamAttempt,
  savePeriodicExamAnswer,
  submitPeriodicExamAttempt,
} from '../lib/periodicExamsApi'
import type { PeriodicExamAttempt } from '../types/periodicExams'

vi.mock('../lib/periodicExamsApi', () => ({
  advancePeriodicExamAttempt: vi.fn(),
  fetchPeriodicExamAttempt: vi.fn(),
  savePeriodicExamAnswer: vi.fn(),
  submitPeriodicExamAttempt: vi.fn(),
}))

function makeAttempt(overrides: Partial<PeriodicExamAttempt> = {}): PeriodicExamAttempt {
  return {
    id: 41,
    attempt_number: 1,
    submitted: false,
    current_question_index: 0,
    total_questions: 2,
    remaining_seconds: 17,
    current_question: {
      id: 501,
      question_text: 'Which action is safest?',
      question_type: 'SINGLE_CHOICE',
      marks: 1,
      choices: [{ key: 'A', text: 'Verify first' }, { key: 'B', text: 'Send immediately' }],
      selected_option_keys: [],
    },
    ...overrides,
  }
}

function renderAttempt() {
  return render(
    <MemoryRouter initialEntries={['/periodic-exam/attempt/41']}>
      <Routes>
        <Route path="/periodic-exam/attempt/:attemptId" element={<PeriodicExamAttemptPage />} />
        <Route path="/periodic-exam/attempt/:attemptId/result" element={<p>result screen</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PeriodicExamAttemptPage', () => {
  beforeEach(() => {
    vi.mocked(fetchPeriodicExamAttempt).mockReset().mockResolvedValue(makeAttempt())
    vi.mocked(savePeriodicExamAnswer).mockReset().mockImplementation(async (_id, _index, keys) => makeAttempt({
      current_question: { ...makeAttempt().current_question!, selected_option_keys: keys },
    }))
    vi.mocked(advancePeriodicExamAttempt).mockReset().mockResolvedValue(makeAttempt({
      current_question_index: 1,
      remaining_seconds: 17,
      current_question: { ...makeAttempt().current_question!, id: 502, question_text: 'Second question' },
    }))
    vi.mocked(submitPeriodicExamAttempt).mockReset().mockResolvedValue(makeAttempt({ submitted: true, current_question: undefined, score_percent: '50.00', passed: false }))
  })

  it('resumes by fetching the attempt, uses server seconds, saves on change, and has no previous control', async () => {
    renderAttempt()
    expect(await screen.findByText('Which action is safest?')).toBeInTheDocument()
    expect(screen.getByLabelText('17 seconds remaining')).toBeInTheDocument()
    expect(fetchPeriodicExamAttempt).toHaveBeenCalledWith(41)
    expect(screen.queryByRole('button', { name: /previous/i })).not.toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Verify first'))
    await waitFor(() => expect(savePeriodicExamAnswer).toHaveBeenCalledWith(41, 0, ['A']))
  })

  it('uses the server response to auto-lock and move to the next question after expiry', async () => {
    vi.mocked(fetchPeriodicExamAttempt)
      .mockResolvedValueOnce(makeAttempt({ remaining_seconds: 0 }))
      .mockResolvedValueOnce(makeAttempt({
        current_question_index: 1,
        remaining_seconds: 17,
        current_question: { ...makeAttempt().current_question!, id: 502, question_text: 'Server advanced question' },
      }))
    renderAttempt()
    expect(await screen.findByText('Server advanced question')).toBeInTheDocument()
    expect(fetchPeriodicExamAttempt).toHaveBeenCalledTimes(2)
  })

  it('advances forward and submits through the final-question endpoint', async () => {
    const { unmount } = renderAttempt()
    fireEvent.click(await screen.findByRole('button', { name: 'Save and continue' }))
    await waitFor(() => expect(advancePeriodicExamAttempt).toHaveBeenCalledWith(41, 0))
    unmount()

    vi.mocked(fetchPeriodicExamAttempt).mockResolvedValue(makeAttempt({ current_question_index: 1, total_questions: 2 }))
    renderAttempt()
    fireEvent.click(await screen.findByRole('button', { name: 'Submit exam' }))
    await waitFor(() => expect(submitPeriodicExamAttempt).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('result screen')).toBeInTheDocument()
  })

  it('retries a failed final submission without firing duplicate requests', async () => {
    vi.mocked(fetchPeriodicExamAttempt).mockResolvedValue(makeAttempt({ current_question_index: 1, total_questions: 2 }))
    vi.mocked(submitPeriodicExamAttempt)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(makeAttempt({ submitted: true, current_question: undefined, score_percent: '50.00', passed: false }))
    renderAttempt()
    fireEvent.click(await screen.findByRole('button', { name: 'Submit exam' }))
    expect(await screen.findByText(/server could not confirm/i)).toBeInTheDocument()
    expect(submitPeriodicExamAttempt).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(submitPeriodicExamAttempt).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('result screen')).toBeInTheDocument()
  })
})
