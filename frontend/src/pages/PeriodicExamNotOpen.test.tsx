import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PeriodicExamIntroPage } from './PeriodicExamIntroPage'
import { PeriodicExamDashboardCard } from '../components/PeriodicExamDashboardCard'
import { ApiError } from '../lib/apiClient'
import { fetchPeriodicExamSummary } from '../lib/periodicExamsApi'
import type { PeriodicExamAvailability } from '../types/periodicExams'

const state = vi.hoisted(() => ({ availability: null as PeriodicExamAvailability | null }))

vi.mock('../context/usePeriodicExamAvailability', () => ({
  usePeriodicExamAvailability: () => ({ availability: state.availability, isLoading: false }),
}))

vi.mock('../lib/periodicExamsApi', () => ({
  fetchPeriodicExamSummary: vi.fn(),
  startPeriodicExamAttempt: vi.fn(),
}))

const openCycle = {
  id: 1,
  sequence: 1,
  frequency_snapshot: 'MONTHLY' as const,
  display_label: '2083 Kartik',
  starts_at: '2026-10-17T18:15:00Z',
  ends_at: '2026-11-16T18:15:00Z',
  start_date_ad: '2026-10-18',
  end_date_ad: '2026-11-16',
  questions_per_exam: 30,
  pass_mark_percent: 60,
  seconds_per_question: 60,
  max_attempts_per_cycle: 2,
  reminders_enabled: false,
  reminder_days_before_end: [7, 2],
}

function renderIntro() {
  return render(<MemoryRouter><PeriodicExamIntroPage /></MemoryRouter>)
}

describe('Periodic Exam before a cycle is open', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows when the first cycle opens instead of an error, without requesting the summary', () => {
    state.availability = {
      enabled: true,
      current_cycle: null,
      upcoming_cycle: { starts_at: '2026-10-17T18:15:00Z', start_date_ad: '2026-10-18', display_label: '2083 Kartik' },
    }
    renderIntro()
    expect(screen.getByText(/Your first Periodic Exam \(2083 Kartik\) opens on/)).toBeInTheDocument()
    expect(screen.queryByText(/could not be loaded/)).not.toBeInTheDocument()
    expect(fetchPeriodicExamSummary).not.toHaveBeenCalled()
  })

  it('says no cycle is open when there is no upcoming start to announce', () => {
    state.availability = { enabled: true, current_cycle: null, upcoming_cycle: null }
    renderIntro()
    expect(screen.getByText('No Periodic Exam cycle is open right now.')).toBeInTheDocument()
  })

  it('shows the server reason when the learner is not in the current cycle', async () => {
    state.availability = { enabled: true, current_cycle: openCycle }
    vi.mocked(fetchPeriodicExamSummary).mockRejectedValue(
      new ApiError(403, { detail: 'You are not eligible for this cycle.', code: 'NOT_ELIGIBLE' }),
    )
    renderIntro()
    expect(await screen.findByText(/not included in the current Periodic Exam cycle/)).toBeInTheDocument()
  })

  it('falls back to the server detail, then a generic message', async () => {
    state.availability = { enabled: true, current_cycle: openCycle }
    vi.mocked(fetchPeriodicExamSummary).mockRejectedValueOnce(new ApiError(400, { detail: 'Something specific.' }))
    const { unmount } = renderIntro()
    expect(await screen.findByText('Something specific.')).toBeInTheDocument()
    unmount()

    vi.mocked(fetchPeriodicExamSummary).mockRejectedValueOnce(new Error('network'))
    renderIntro()
    expect(await screen.findByText('Periodic Exam details could not be loaded. Please try again.')).toBeInTheDocument()
  })

  it('dashboard card shows the opening date and no Start link before the first cycle', async () => {
    state.availability = {
      enabled: true,
      current_cycle: null,
      upcoming_cycle: { starts_at: '2026-10-17T18:15:00Z', start_date_ad: '2026-10-18', display_label: '2083 Kartik' },
    }
    render(<MemoryRouter><PeriodicExamDashboardCard /></MemoryRouter>)
    expect(screen.getByText(/opens on/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Start' })).not.toBeInTheDocument()
    await waitFor(() => expect(fetchPeriodicExamSummary).not.toHaveBeenCalled())
  })
})
