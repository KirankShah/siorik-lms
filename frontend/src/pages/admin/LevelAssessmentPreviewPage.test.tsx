import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LevelAssessmentPreviewPage } from './LevelAssessmentPreviewPage'
import * as levelAssessmentsApi from '../../lib/levelAssessmentsApi'
import type { LevelAssessmentPreview } from '../../types/levelAssessments'

vi.mock('../../lib/levelAssessmentsApi')

function makePreview(): LevelAssessmentPreview {
  return {
    assessment_level: {
      id: 1,
      organization: { id: 1, name: 'Acme', slug: 'acme', logo: null, is_active: true },
      name: 'officer',
      name_display: 'Officer Level',
      pass_threshold: 70,
      questions_per_attempt: 2,
      timing_mode: 'PER_QUESTION',
      seconds_per_question: 60,
      total_exam_minutes: 60,
    },
    questions: [
      {
        id: 1,
        question_set: 1,
        question_set_label: 'Set 1',
        assessment_level_name: 'Officer Level',
        question_text: 'First question?',
        question_type: 'SINGLE_CHOICE',
        options: { A: 'Alpha', B: 'Beta', C: '', D: '', E: '' },
        correct_answers: ['A'],
        marks: 1,
        explanation: '',
        feedback_correct: '',
        feedback_incorrect: '',
      },
      {
        id: 2,
        question_set: 1,
        question_set_label: 'Set 1',
        assessment_level_name: 'Officer Level',
        question_text: 'Second question?',
        question_type: 'SINGLE_CHOICE',
        options: { A: 'Gamma', B: 'Delta', C: '', D: '', E: '' },
        correct_answers: ['B'],
        marks: 1,
        explanation: '',
        feedback_correct: '',
        feedback_incorrect: '',
      },
    ],
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin/level-assessment-preview/1']}>
      <Routes>
        <Route path="/admin/level-assessment-preview/:levelId" element={<LevelAssessmentPreviewPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LevelAssessmentPreviewPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(levelAssessmentsApi.previewLevelAssessment).mockResolvedValue(makePreview())
  })

  it('draws once on load and lets an admin move freely both ways without ever starting a real attempt', async () => {
    renderPage()

    expect(await screen.findByText('First question?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Second question?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
    expect(await screen.findByText('First question?')).toBeInTheDocument()

    expect(levelAssessmentsApi.previewLevelAssessment).toHaveBeenCalledTimes(1)
  })

  it('shows the correct answer key immediately, with no submit action', async () => {
    renderPage()

    await screen.findByText('First question?')
    expect(screen.getByText('Alpha').closest('li')).toHaveClass('border-emerald-300')
    expect(screen.getByText('Beta').closest('li')).not.toHaveClass('border-emerald-300')
    expect(screen.queryByRole('button', { name: /submit/i })).not.toBeInTheDocument()
  })
})
