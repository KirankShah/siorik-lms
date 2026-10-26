import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LeaderboardWidget } from './LeaderboardWidget'
import type { LeaderboardEntry } from '../types/gamification'

const mockAuth = vi.hoisted(() => ({ userId: 1, role: 'LEARNER' }))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: mockAuth.userId, role: mockAuth.role } }),
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
  quizzes_completed: 2,
  quizzes_required: 2,
  latest_periodic_exam_score: '70.00',
  knowledge_score: '74.00',
  is_ranked: true,
  last_assessed_at: '2026-10-08T06:00:00Z',
  certificates_earned_count: 1,
  level_assessments_passed_count: 1,
  updated_at: '2026-10-08T06:00:00Z',
}

function leaderboardEntry(
  user_id: number,
  first_name: string,
  knowledge_score: string | null,
  latest_periodic_exam_score: string | null,
  last_assessed_at: string | null,
): LeaderboardEntry {
  return {
    ...entry,
    user_id,
    first_name,
    knowledge_score,
    latest_periodic_exam_score,
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
    expect(screen.getByText('Overall Score = 40% Path Quiz Score + 60% Latest Periodic Exam')).toBeInTheDocument()
    expect(screen.getByText('Knowledge Leaderboard')).toBeInTheDocument()
  })

  it('explains why an eligible ranking is not available yet', () => {
    render(<LeaderboardWidget entries={[]} />)

    expect(screen.getByText(/Complete a Periodic Exam to join the leaderboard/)).toBeInTheDocument()
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

    expect(screen.getByText('My Rank').parentElement).toHaveTextContent('6th')
    expect(screen.getByText('Current Knowledge').parentElement).toHaveTextContent('74%')
    expect(screen.getAllByText('Last Assessed')[0].parentElement).toHaveTextContent('7 Oct 2026')

    const table = screen.getByRole('table')
    const displayedRows = within(table).getAllByRole('row').slice(1)
    expect(displayedRows).toHaveLength(5)
    for (const name of ['Rank One', 'Rank Two', 'Rank Three', 'Rank Four', 'Rank Five']) {
      expect(displayedRows.some((row) => row.textContent?.includes(name))).toBe(true)
    }
    expect(within(table).queryByText('Not Assessed')).not.toBeInTheDocument()
    expect(screen.getByText(/Your position: 6th/)).toBeInTheDocument()
    expect(screen.getByText(/Asha Gurung/)).toBeInTheDocument()
  })

  it('shows a clear card state when the learner has not taken a periodic exam', () => {
    mockAuth.userId = 7
    render(<LeaderboardWidget entries={[entry, leaderboardEntry(7, 'Not Assessed', null, null, null)]} />)

    expect(screen.getAllByText('Not yet assessed')).toHaveLength(3)
    expect(screen.getByText('Current Knowledge').parentElement).not.toHaveTextContent('—')
  })

  it('shows a zero path score when assigned questions are unanswered', () => {
    mockAuth.userId = 8
    const pending = leaderboardEntry(8, 'Quiz Pending', '48.00', '80.00', '2026-10-09T06:00:00Z')
    pending.current_course_quiz_average = '0.00'
    pending.quizzes_completed = 1
    pending.quizzes_required = 2
    render(
      <LeaderboardWidget
        entries={[entry, pending]}
      />,
    )

    expect(screen.queryByText('Not yet assessed')).not.toBeInTheDocument()
    expect(screen.getByText('My Rank').parentElement).toHaveTextContent('2nd')
    expect(screen.getByText('Current Knowledge').parentElement).toHaveTextContent('48%')
    expect(screen.getAllByText('Last Assessed')[0].parentElement).toHaveTextContent('9 Oct 2026')
    const rows = within(screen.getByRole('table')).getAllByRole('row')
    const pendingRow = rows[rows.length - 1]
    const pendingCells = within(pendingRow).getAllByRole('cell')
    expect(pendingCells[3]).toHaveTextContent('0%')
    expect(pendingCells[4]).toHaveTextContent('80%')
    expect(pendingCells[5]).toHaveTextContent('48%')
  })

  it('shows a useful card state for an admin without a learner score', () => {
    mockAuth.userId = 9
    mockAuth.role = 'ORG_ADMIN'
    render(<LeaderboardWidget entries={[]} />)

    expect(screen.getAllByText('No learner score')).toHaveLength(3)
    expect(screen.queryByText('Not yet assessed')).not.toBeInTheDocument()
  })
})
