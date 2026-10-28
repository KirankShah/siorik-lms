import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PeriodicExamIntroPage } from './PeriodicExamIntroPage'
import { PeriodicExamResultPage } from './PeriodicExamResultPage'
import {
  fetchPeriodicExamResult,
  fetchPeriodicExamSummary,
  startPeriodicExamAttempt,
} from '../lib/periodicExamsApi'

vi.mock('../context/usePeriodicExamAvailability', () => ({
  usePeriodicExamAvailability: () => ({
    availability: {
      enabled: true,
      current_cycle: {
        id: 1,
        sequence: 1,
        frequency_snapshot: 'MONTHLY',
        display_label: 'Shrawan 2083',
        starts_at: '2026-07-17T00:00:00+05:45',
        ends_at: '2026-08-17T00:00:00+05:45',
        start_date_ad: '2026-07-17',
        end_date_ad: '2026-08-16',
        questions_per_exam: 30,
        pass_mark_percent: 60,
        seconds_per_question: 60,
        max_attempts_per_cycle: 2,
        reminders_enabled: false,
        reminder_days_before_end: [7, 2],
      },
    },
  }),
}))

vi.mock('../lib/periodicExamsApi', () => ({
  fetchPeriodicExamSummary: vi.fn(),
  startPeriodicExamAttempt: vi.fn(),
  fetchPeriodicExamResult: vi.fn(),
}))

const summary = {
  cycle: { id: 1, display_label: 'Shrawan 2083', starts_at: '2026-07-17T00:00:00+05:45', ends_at: '2026-08-17T00:00:00+05:45', questions_per_exam: 30, pass_mark_percent: 60, seconds_per_question: 60, max_attempts_per_cycle: 2 },
  status: 'PENDING' as const,
  attempted: false,
  completed: false,
  attempts_used: 0,
  attempts_remaining: 2,
  best_score_percent: null,
  passed: false,
  open_attempt_id: null,
  last_completed_attempt_id: null,
  can_start: true,
  reason_code: null,
}

describe('Periodic Exam introduction and result', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchPeriodicExamSummary).mockResolvedValue(summary)
    vi.mocked(startPeriodicExamAttempt).mockResolvedValue({
      id: 91, attempt_number: 1, submitted: false, current_question_index: 0,
      total_questions: 30, remaining_seconds: 60,
    })
  })

  it('shows assigned cycle values, rules, and starts an attempt', async () => {
    render(
      <MemoryRouter initialEntries={['/periodic-exam']}>
        <Routes>
          <Route path="/periodic-exam" element={<PeriodicExamIntroPage />} />
          <Route path="/periodic-exam/attempt/:attemptId" element={<p>attempt screen</p>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByText('Shrawan 2083 closes on Aug 17, 2026.')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
    expect(screen.getByText('60s')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText(/cannot return to an earlier question/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Start exam' }))
    await waitFor(() => expect(screen.getByText('attempt screen')).toBeInTheDocument())
    expect(startPeriodicExamAttempt).toHaveBeenCalledTimes(1)
  })

  it('offers resume instead of creating another attempt', async () => {
    vi.mocked(fetchPeriodicExamSummary).mockResolvedValue({ ...summary, status: 'IN_PROGRESS', open_attempt_id: 77, can_start: false, reason_code: 'ATTEMPT_IN_PROGRESS' })
    render(
      <MemoryRouter initialEntries={['/periodic-exam']}>
        <Routes>
          <Route path="/periodic-exam" element={<PeriodicExamIntroPage />} />
          <Route path="/periodic-exam/attempt/:attemptId" element={<p>resumed</p>} />
        </Routes>
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Resume exam' }))
    expect(await screen.findByText('resumed')).toBeInTheDocument()
    expect(startPeriodicExamAttempt).not.toHaveBeenCalled()
  })

  it('shows only score/pass state and attempt aggregates on the result page', async () => {
    vi.mocked(fetchPeriodicExamResult).mockResolvedValue({ score_percent: '80.00', passed: true })
    vi.mocked(fetchPeriodicExamSummary).mockResolvedValue({ ...summary, status: 'PASSED', attempted: true, completed: true, attempts_used: 1, attempts_remaining: 1, best_score_percent: '80.00', passed: true, last_completed_attempt_id: 91, can_start: false, reason_code: 'ALREADY_PASSED' })
    render(
      <MemoryRouter initialEntries={['/periodic-exam/attempt/91/result']}>
        <Routes><Route path="/periodic-exam/attempt/:attemptId/result" element={<PeriodicExamResultPage />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: 'Passed' })).toBeInTheDocument()
    expect(screen.getAllByText('80.00%')).toHaveLength(2)
    expect(screen.getByText('Answer review is not available for Periodic Exams.')).toBeInTheDocument()
    expect(screen.queryByText(/correct answer/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/choice/i)).not.toBeInTheDocument()
  })
})
