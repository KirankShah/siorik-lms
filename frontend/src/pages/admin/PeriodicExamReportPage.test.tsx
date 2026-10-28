import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PeriodicExamReportPage } from './PeriodicExamReportPage'
import * as api from '../../lib/periodicExamsApi'

const mocks = vi.hoisted(() => ({ role: 'ORG_ADMIN' }))
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { role: mocks.role } }),
}))
vi.mock('../../lib/periodicExamsApi', () => ({
  fetchPlatformPeriodicExamOrganizations: vi.fn(),
  fetchPeriodicExamReportCycles: vi.fn(),
  fetchPeriodicExamReport: vi.fn(),
  downloadPeriodicExamReportCsv: vi.fn(),
  downloadPeriodicExamReportXlsx: vi.fn(),
}))

const cycle = { id: 10, display_label: 'Shrawan 2083', start_date_ad: '2026-07-17', end_date_ad: '2026-08-16' }
const row = {
  staff_name: 'प्रगति Learner', email: 'learner@example.com', level: 'Officer',
  branch_department: 'Risk', cycle: 'Shrawan 2083', attempted: true, completed: true,
  attempts_used: 2, best_score: 80, status: 'Passed' as const,
  last_attempt_date: '2026-07-20T10:00:00+05:45',
  attempt_scores: [50, 80],
}

describe('PeriodicExamReportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.role = 'ORG_ADMIN'
    vi.mocked(api.fetchPeriodicExamReportCycles).mockResolvedValue([cycle])
    vi.mocked(api.fetchPeriodicExamReport).mockResolvedValue({ count: 1, page: 1, page_size: 50, results: [row] })
    vi.mocked(api.fetchPlatformPeriodicExamOrganizations).mockResolvedValue([])
  })

  it('renders report data, filters, and both downloads', async () => {
    render(<PeriodicExamReportPage />)
    expect(await screen.findByText('प्रगति Learner')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Passed' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'प्रगति' } })
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'Passed' } })
    await waitFor(() => expect(api.fetchPeriodicExamReport).toHaveBeenLastCalledWith(0, {
      organizationId: undefined, search: 'प्रगति', status: 'Passed', page: 1,
    }))
    fireEvent.click(screen.getByRole('button', { name: 'Download CSV' }))
    fireEvent.click(screen.getByRole('button', { name: 'Download Excel' }))
    expect(api.downloadPeriodicExamReportCsv).toHaveBeenCalledWith(0, undefined)
    expect(api.downloadPeriodicExamReportXlsx).toHaveBeenCalledWith(0, undefined)
  })

  it('shows empty and error states', async () => {
    vi.mocked(api.fetchPeriodicExamReportCycles).mockResolvedValueOnce([])
    const { unmount } = render(<PeriodicExamReportPage />)
    expect(await screen.findByText('No Periodic Exam cycles are available.')).toBeInTheDocument()
    unmount()
    vi.mocked(api.fetchPeriodicExamReportCycles).mockRejectedValueOnce(new Error('offline'))
    render(<PeriodicExamReportPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('cycles could not be loaded')
  })

  it('requires a platform organization selector and scopes requests to it', async () => {
    mocks.role = 'PLATFORM_ADMIN'
    vi.mocked(api.fetchPlatformPeriodicExamOrganizations).mockResolvedValue([
      { id: 7, name: 'Lumbini', slug: 'lumbini', is_active: true, periodic_exam_enabled: true, periodic_exam_enabled_from: null, periodic_exam_question_counts: [] },
    ])
    render(<PeriodicExamReportPage />)
    expect(await screen.findByLabelText('Organization')).toHaveValue('7')
    await waitFor(() => expect(api.fetchPeriodicExamReportCycles).toHaveBeenCalledWith(7))
    await waitFor(() => expect(api.fetchPeriodicExamReport).toHaveBeenCalledWith(0, expect.objectContaining({ organizationId: 7 })))
  })
})
