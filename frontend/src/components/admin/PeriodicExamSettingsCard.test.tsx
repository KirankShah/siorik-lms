import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PeriodicExamSettingsCard } from './PeriodicExamSettingsCard'
import * as api from '../../lib/periodicExamsApi'

vi.mock('../../lib/periodicExamsApi', () => ({
  fetchPeriodicExamSettings: vi.fn(), fetchPeriodicExamReadiness: vi.fn(), updatePeriodicExamSettings: vi.fn(),
}))

describe('PeriodicExamSettingsCard', () => {
  beforeEach(() => {
    vi.mocked(api.fetchPeriodicExamSettings).mockResolvedValue({
      organization_id: 1, enabled: true, frequency: 'MONTHLY', pending_frequency: null,
      pending_frequency_effective_at: null, questions_per_exam: 30, pass_mark_percent: 60,
      seconds_per_question: 60, max_attempts_per_cycle: 2, reminders_enabled: false,
      reminder_days_before_end: [7, 2], configuration_version: 1, enabled_from: null,
      current_cycle: {
        id: 1, sequence: 1, frequency_snapshot: 'MONTHLY', display_label: 'Shrawan 2083',
        starts_at: '2026-07-17T00:00:00+05:45', ends_at: '2026-08-17T00:00:00+05:45',
        start_date_ad: '2026-07-17', end_date_ad: '2026-08-16', questions_per_exam: 30,
        pass_mark_percent: 60, seconds_per_question: 60, max_attempts_per_cycle: 2,
        reminders_enabled: false, reminder_days_before_end: [7, 2],
      }, question_counts: [],
    })
    vi.mocked(api.fetchPeriodicExamReadiness).mockResolvedValue({
      organization_id: 1, cycle_id: 1, as_of: '2026-07-20T00:00:00Z',
      levels: [{ level: 'officer', level_display: 'Officer', unique_question_count: 45, eligible_learner_count: 120, questions_per_exam: 30, can_form_full_exam: true, note: '' }],
    })
  })

  it('separates the frozen current snapshot from next-cycle settings and neutral readiness information', async () => {
    render(<PeriodicExamSettingsCard />)
    expect(await screen.findByText(/Current cycle:/)).toHaveTextContent('Shrawan 2083')
    expect(screen.getByText('Changes apply from the next cycle only.')).toBeInTheDocument()
    expect(screen.getByText(/Officer: 45 questions · 120 eligible learners/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save settings' })).toBeInTheDocument()
  })
})
