import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PeriodicExamDashboardCard } from './PeriodicExamDashboardCard'
import { Sidebar } from './shell/Sidebar'
import { PeriodicExamRoute } from '../routes/PeriodicExamRoute'
import { fetchPeriodicExamSummary } from '../lib/periodicExamsApi'

const mocks = vi.hoisted(() => ({
  role: 'LEARNER',
  enabled: true,
  isLoading: false,
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, email: 'learner@example.com', role: mocks.role, preferred_narration_language: 'en' },
    logout: vi.fn(),
    updateNarrationLanguage: vi.fn(),
  }),
}))

vi.mock('../context/usePeriodicExamAvailability', () => ({
  usePeriodicExamAvailability: () => ({
    availability: { enabled: mocks.enabled, current_cycle: { display_label: '2083 Shrawan' } },
    isLoading: mocks.isLoading,
    refreshAvailability: vi.fn(),
  }),
}))

vi.mock('../lib/periodicExamsApi', () => ({ fetchPeriodicExamSummary: vi.fn() }))

const summary = {
  cycle: { id: 1, display_label: '2083 Shrawan', starts_at: '2026-07-17T00:00:00+05:45', ends_at: '2026-08-17T00:00:00+05:45' },
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

describe('Periodic Exam visibility', () => {
  beforeEach(() => {
    mocks.role = 'LEARNER'
    mocks.enabled = true
    mocks.isLoading = false
    vi.mocked(fetchPeriodicExamSummary).mockResolvedValue(summary)
  })

  it('shows learner navigation only when enabled and never changes other roles', () => {
    const { rerender } = render(<MemoryRouter><Sidebar /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Periodic Exam' })).toBeInTheDocument()

    mocks.enabled = false
    rerender(<MemoryRouter><Sidebar /></MemoryRouter>)
    expect(screen.queryByRole('link', { name: 'Periodic Exam' })).not.toBeInTheDocument()

    mocks.enabled = true
    mocks.role = 'INSTRUCTOR'
    rerender(<MemoryRouter><Sidebar /></MemoryRouter>)
    expect(screen.queryByRole('link', { name: 'Periodic Exam' })).not.toBeInTheDocument()
  })

  it('shows no card when off and shows cycle, status, attempts, score, and action when on', async () => {
    mocks.enabled = false
    const { rerender } = render(<MemoryRouter><PeriodicExamDashboardCard /></MemoryRouter>)
    expect(screen.queryByTestId('periodic-exam-dashboard-card')).not.toBeInTheDocument()

    mocks.enabled = true
    rerender(<MemoryRouter><PeriodicExamDashboardCard /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('2083 Shrawan')).toBeInTheDocument())
    expect(screen.getByText('Not started')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start' })).toHaveAttribute('href', '/periodic-exam')
  })

  it('renders a not-available page for a disabled direct route', () => {
    mocks.enabled = false
    render(
      <MemoryRouter initialEntries={['/periodic-exam']}>
        <Routes>
          <Route element={<PeriodicExamRoute />}>
            <Route path="/periodic-exam" element={<p>secret exam</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Periodic Exam is not available' })).toBeInTheDocument()
    expect(screen.queryByText('secret exam')).not.toBeInTheDocument()
  })

  it('shows a clear cannot-start reason', async () => {
    vi.mocked(fetchPeriodicExamSummary).mockResolvedValue({
      ...summary,
      can_start: false,
      reason_code: 'INSUFFICIENT_POOL',
    })
    render(<MemoryRouter><PeriodicExamDashboardCard /></MemoryRouter>)
    expect(await screen.findByText('A full exam cannot be formed for your assigned level yet.')).toBeInTheDocument()
  })
})
