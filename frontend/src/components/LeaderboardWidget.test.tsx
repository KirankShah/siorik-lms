import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LeaderboardWidget } from './LeaderboardWidget'
import type { LeaderboardEntry } from '../types/gamification'

const mockAuth = vi.hoisted(() => ({ userId: 1 }))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: mockAuth.userId, role: 'LEARNER' } }),
}))

const entry: LeaderboardEntry = {
  user_id: 1,
  first_name: 'Asha',
  last_name: 'Gurung',
  assessment_level: 'officer',
  assessment_level_display: 'Officer Level',
  total_points: 420,
  courses_completed_count: 2,
  average_quiz_score: '92.00',
  current_course_quiz_average: '80.00',
  latest_level_assessment_score: '70.00',
  knowledge_score: '74.00',
  last_assessed_at: '2026-10-08T06:00:00Z',
  certificates_earned_count: 1,
  level_assessments_passed_count: 1,
  updated_at: '2026-10-08T06:00:00Z',
}

function leaderboardEntry(
  user_id: number,
  first_name: string,
  knowledge_score: string | null,
  latest_level_assessment_score: string | null,
  last_assessed_at: string | null,
): LeaderboardEntry {
  return {
    ...entry,
    user_id,
    first_name,
    knowledge_score,
    latest_level_assessment_score,
    last_assessed_at,
  } as LeaderboardEntry
}

describe('LeaderboardWidget', () => {
  it('shows the current-knowledge calculation and its latest inputs', () => {
    render(<LeaderboardWidget entries={[entry]} />)

    expect(screen.getByText('Current Knowledge')).toBeInTheDocument()
    expect(screen.getAllByText('74%')).toHaveLength(2)
    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('70%')).toBeInTheDocument()
    expect(screen.getByText('Officer Level')).toBeInTheDocument()
    expect(screen.getByText('Knowledge Score = 40% Course Quiz Average + 60% Latest Level Assessment')).toBeInTheDocument()
  })

  it('explains why an eligible ranking is not available yet', () => {
    render(<LeaderboardWidget entries={[]} />)

    expect(screen.getByText(/Complete a course quiz and a Level Assessment/)).toBeInTheDocument()
  })

  it('shows the learner card metrics and own row below the Top 5 while excluding unassessed learners from ranked places', () => {
    mockAuth.userId = 1
    const entries = [
      leaderboardEntry(2, 'Rank One', '99.00', '99.00', '2026-10-08T06:00:00Z'),
      leaderboardEntry(3, 'Rank Two', '95.00', '95.00', '2026-10-08T06:00:00Z'),
      leaderboardEntry(4, 'Rank Three', '90.00', '90.00', '2026-10-08T06:00:00Z'),
      leaderboardEntry(5, 'Rank Four', '85.00', '85.00', '2026-10-08T06:00:00Z'),
      leaderboardEntry(6, 'Rank Five', '80.00', '80.00', '2026-10-08T06:00:00Z'),
      leaderboardEntry(1, 'Asha', '74.00', '70.00', '2026-10-07T06:00:00Z'),
      leaderboardEntry(7, 'Not Assessed', null, null, null),
    ]

    render(<LeaderboardWidget entries={entries} />)

    expect(screen.getByText('My Rank').parentElement).toHaveTextContent('6')
    expect(screen.getByText('Current Knowledge').parentElement).toHaveTextContent('74%')
    expect(screen.getAllByText('Last Assessed')[0].parentElement).toHaveTextContent('7 Oct 2026')

    const table = screen.getByRole('table')
    const displayedRows = within(table).getAllByRole('row').slice(1)
    expect(displayedRows).toHaveLength(5)
    for (const name of ['Rank One', 'Rank Two', 'Rank Three', 'Rank Four', 'Rank Five']) {
      expect(displayedRows.some((row) => row.textContent?.includes(name))).toBe(true)
    }
    expect(screen.getByText(/Your position: 6th/)).toBeInTheDocument()
    expect(screen.getByText('Asha Gurung')).toBeInTheDocument()
  })

  it('shows a clear card state when the learner has not taken a level assessment', () => {
    mockAuth.userId = 7
    render(<LeaderboardWidget entries={[entry, leaderboardEntry(7, 'Not Assessed', null, null, null)]} />)

    expect(screen.getAllByText('Not yet assessed')).toHaveLength(3)
    expect(screen.getByText('Current Knowledge').parentElement).not.toHaveTextContent('—')
  })

  it('does not call a learner unassessed when only the course quiz is missing', () => {
    mockAuth.userId = 8
    render(
      <LeaderboardWidget
        entries={[entry, leaderboardEntry(8, 'Quiz Pending', null, '80.00', '2026-10-09T06:00:00Z')]}
      />,
    )

    expect(screen.queryByText('Not yet assessed')).not.toBeInTheDocument()
    expect(screen.getByText('My Rank').parentElement).toHaveTextContent('Not ranked yet')
    expect(screen.getByText('Current Knowledge').parentElement).toHaveTextContent('Complete a course quiz')
    expect(screen.getAllByText('Last Assessed')[0].parentElement).toHaveTextContent('9 Oct 2026')
  })
})
