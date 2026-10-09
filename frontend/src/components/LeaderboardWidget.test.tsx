import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LeaderboardWidget } from './LeaderboardWidget'
import type { LeaderboardEntry } from '../types/gamification'

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1 } }),
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

    expect(screen.getByText(/Complete all assigned course quizzes and a Level Assessment/)).toBeInTheDocument()
  })
})
