import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LevelAssessmentPage } from './LevelAssessmentPage'
import * as levelAssessmentsApi from '../lib/levelAssessmentsApi'
import type { AssessmentLevelSummary, LevelAssessmentAttempt, MyAssessmentLevelStatus } from '../types/levelAssessments'

vi.mock('../lib/levelAssessmentsApi')

// Real time, not mocked — a self-rescheduling setTimeout effect (the
// countdown reschedules itself every tick) doesn't compose reliably with
// React's async act() + fake timers: act's flush loop drains the whole
// chain to completion regardless of the requested advance, since it can't
// tell "this effect's timer is done" from "keep flushing". Ten seconds
// gives comfortable margin over test-harness overhead (module transform,
// mock resolution, render) while these tests wait on the real clock.
const SECONDS_PER_QUESTION = 10

const assessmentLevel: AssessmentLevelSummary = {
  id: 1,
  organization: { id: 1, name: 'Acme Bank', slug: 'acme-bank', logo: null, is_active: true },
  name: 'officer',
  name_display: 'Officer Level',
  pass_threshold: 70,
  questions_per_attempt: 2,
  seconds_per_question: SECONDS_PER_QUESTION,
}

function buildAttempt(): LevelAssessmentAttempt {
  return {
    id: 500,
    user: 1,
    assessment_level: 1,
    assessment_level_name: 'Officer Level',
    pass_threshold: 70,
    started_at: '2026-01-01T00:00:00Z',
    submitted_at: null,
    score_percent: '0.00',
    passed: false,
    questions: [
      {
        id: 1,
        question_text: 'First question?',
        question_type: 'SINGLE_CHOICE',
        marks: 1,
        choices: [
          { id: 10, choice_text: 'Choice A', order: 1 },
          { id: 11, choice_text: 'Choice B', order: 2 },
        ],
      },
      {
        id: 2,
        question_text: 'Second question?',
        question_type: 'SINGLE_CHOICE',
        marks: 1,
        choices: [
          { id: 20, choice_text: 'Choice C', order: 1 },
          { id: 21, choice_text: 'Choice D', order: 2 },
        ],
      },
    ],
    answers: [],
  }
}

const notStartedStatus: MyAssessmentLevelStatus = {
  assigned: true,
  assessment_level: assessmentLevel,
  status: 'NOT_STARTED',
  open_attempt_id: null,
}

async function startAssessment() {
  vi.mocked(levelAssessmentsApi.fetchMyAssessmentLevel).mockResolvedValue(notStartedStatus)
  vi.mocked(levelAssessmentsApi.startLevelAssessmentAttempt).mockResolvedValue(buildAttempt())

  render(
    <MemoryRouter>
      <LevelAssessmentPage />
    </MemoryRouter>,
  )
  fireEvent.click(await screen.findByRole('button', { name: 'Start Assessment' }))
  await screen.findByText('First question?')
}

describe('LevelAssessmentPage sequential flow', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows one question at a time, with no back/skip control, and gates Next on answering', async () => {
    await startAssessment()

    // Only the current question's content is in the DOM at all — nothing to
    // skip ahead to even by inspecting markup, let alone a visible control.
    expect(screen.queryByText('Second question?')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /previous|back/i })).not.toBeInTheDocument()

    const next = screen.getByRole('button', { name: 'Next' })
    expect(next).toBeDisabled()

    fireEvent.click(screen.getByLabelText('Choice A'))
    expect(next).toBeEnabled()

    fireEvent.click(next)

    expect(await screen.findByText('Second question?')).toBeInTheDocument()
    // Advanced past question 1 — it's gone, and there is still no control
    // that could take the learner back to it.
    expect(screen.queryByText('First question?')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /previous|back/i })).not.toBeInTheDocument()
  })

  it(
    'depletes the countdown bar in real time and freezes it once the question is answered',
    async () => {
      await startAssessment()

      expect(screen.getByText(`${SECONDS_PER_QUESTION}s`)).toBeInTheDocument()

      // Genuine real-time depletion — some seconds in, the readout must be
      // measurably lower than the starting value and not yet zero.
      await waitFor(
        () => {
          const remaining = Number(screen.getByText(/^\d+s$/).textContent!.replace('s', ''))
          expect(remaining).toBeLessThan(SECONDS_PER_QUESTION)
          expect(remaining).toBeGreaterThan(0)
        },
        { timeout: (SECONDS_PER_QUESTION - 1) * 1000 },
      )

      fireEvent.click(screen.getByLabelText('Choice A'))
      const frozenAt = screen.getByText(/^\d+s$/).textContent

      // Frozen once answered — waiting well past when it would otherwise
      // have hit zero must not change the readout, lock the question, or
      // show the timeout message.
      await new Promise((resolve) => setTimeout(resolve, SECONDS_PER_QUESTION * 1000))
      expect(screen.getByText(frozenAt!)).toBeInTheDocument()
      expect(screen.queryByText(/Time's up/)).not.toBeInTheDocument()
    },
    (SECONDS_PER_QUESTION * 2 + 5) * 1000,
  )

  it(
    'locks an unanswered question at zero, records an empty selection for it, and auto-advances',
    async () => {
      const submitted: LevelAssessmentAttempt = {
        ...buildAttempt(),
        submitted_at: '2026-01-01T00:05:00Z',
        passed: true,
        score_percent: '50.00',
      }
      vi.mocked(levelAssessmentsApi.submitLevelAssessmentAttempt).mockResolvedValue(submitted)

      await startAssessment()

      // Never answer question 1 — let its timer run all the way out for real.
      await screen.findByText(
        "Time's up — 0 marks for this question.",
        {},
        { timeout: (SECONDS_PER_QUESTION + 2) * 1000 },
      )
      // Locked: the choice inputs are gone, not just disabled.
      expect(screen.queryByLabelText('Choice A')).not.toBeInTheDocument()

      // Auto-advances on its own after the message delay — no click needed.
      // Assert against Choice C actually being interactive (not just the
      // question 2 heading text, which — unlike the locked-message-vs-
      // choices split — renders unconditionally a render tick before the
      // fresh question's own unlock/reset effect settles).
      await screen.findByLabelText('Choice C', {}, { timeout: 3000 })
      expect(screen.queryByText(/Time's up/)).not.toBeInTheDocument()

      fireEvent.click(screen.getByLabelText('Choice C'))
      fireEvent.click(screen.getByRole('button', { name: 'Finish' }))

      await waitFor(() => expect(levelAssessmentsApi.submitLevelAssessmentAttempt).toHaveBeenCalled())
      const [, payload] = vi.mocked(levelAssessmentsApi.submitLevelAssessmentAttempt).mock.calls[0]
      // Question 1 (timed out) submits an empty selection — 0 marks, since
      // the exact-set-equality grading can never award marks for no answer.
      // Question 2 (answered) submits the learner's actual choice.
      expect(payload).toEqual([
        { question: 1, selected_choices: [] },
        { question: 2, selected_choices: [20] },
      ])
    },
    (SECONDS_PER_QUESTION + 8) * 1000,
  )
})
