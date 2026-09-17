import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LevelAssessmentPage } from './LevelAssessmentPage'
import * as levelAssessmentsApi from '../lib/levelAssessmentsApi'
import type { AssessmentLevelSummary, LevelAssessmentAttempt, MyAssessmentLevelStatus } from '../types/levelAssessments'

vi.mock('../lib/levelAssessmentsApi')

const START_BUTTON_NAME = "I'm Ready, Start Exam"
const CONTINUE_BUTTON_NAME = "I'm Ready, Continue Exam"

// Real time, not mocked — a self-rescheduling setTimeout effect (the
// countdown reschedules itself every tick) doesn't compose reliably with
// React's async act() + fake timers: act's flush loop drains the whole
// chain to completion regardless of the requested advance, since it can't
// tell "this effect's timer is done" from "keep flushing". Ten seconds
// gives comfortable margin over test-harness overhead (module transform,
// mock resolution, render) while these tests wait on the real clock.
const SECONDS_PER_QUESTION = 10
// Same real-clock reasoning for the FIXED_TOTAL tests below. total_exam_minutes
// is minutes-only in the real data model, but nothing stops a test mock from
// using a fractional value — the component converts to seconds and rounds
// (Math.round), so this lands on exactly 10 seconds, same as SECONDS_PER_QUESTION.
const TOTAL_EXAM_SECONDS = 10

const assessmentLevel: AssessmentLevelSummary = {
  id: 1,
  organization: { id: 1, name: 'Acme Bank', slug: 'acme-bank', logo: null, is_active: true },
  name: 'officer',
  name_display: 'Officer Level',
  pass_threshold: 70,
  questions_per_attempt: 2,
  timing_mode: 'PER_QUESTION',
  seconds_per_question: SECONDS_PER_QUESTION,
  total_exam_minutes: 60,
}

const fixedTotalAssessmentLevel: AssessmentLevelSummary = {
  ...assessmentLevel,
  timing_mode: 'FIXED_TOTAL',
  total_exam_minutes: TOTAL_EXAM_SECONDS / 60,
}

function buildAttempt(overrides: Partial<LevelAssessmentAttempt> = {}): LevelAssessmentAttempt {
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
    current_question_index: 0,
    answers_so_far: {},
    remaining_seconds: SECONDS_PER_QUESTION,
    questions: [
      {
        id: 1,
        question_text: 'First question?',
        question_type: 'SINGLE_CHOICE',
        marks: 1,
        removed: false,
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
        removed: false,
        choices: [
          { id: 20, choice_text: 'Choice C', order: 1 },
          { id: 21, choice_text: 'Choice D', order: 2 },
        ],
      },
    ],
    answers: [],
    ...overrides,
  }
}

function buildStatus(
  level: AssessmentLevelSummary,
  overrides: Partial<MyAssessmentLevelStatus> = {},
): MyAssessmentLevelStatus {
  return { assigned: true, assessment_level: level, status: 'NOT_STARTED', open_attempt_id: null, ...overrides }
}

// A minimal stand-in for the backend's own attempt state — save-answer and
// advance both mutate it and echo it back, exactly like the real endpoints,
// so tests that click through multiple questions see realistic responses
// (a fresh remaining_seconds on each PER_QUESTION advance, the running
// answers_so_far map, etc.) instead of a static mock that can't react to
// what the component actually sent.
function setupFakeAttemptBackend(initial: LevelAssessmentAttempt) {
  let current = initial

  vi.mocked(levelAssessmentsApi.startLevelAssessmentAttempt).mockImplementation(async () => current)
  vi.mocked(levelAssessmentsApi.fetchLevelAssessmentAttempt).mockImplementation(async () => current)
  vi.mocked(levelAssessmentsApi.saveLevelAssessmentAnswerProgress).mockImplementation(async (_id, answer) => {
    current = {
      ...current,
      answers_so_far: { ...current.answers_so_far, [String(answer.question)]: answer.selected_choices },
    }
    return current
  })
  vi.mocked(levelAssessmentsApi.advanceLevelAssessmentAttempt).mockImplementation(async (_id, newIndex) => {
    current = { ...current, current_question_index: newIndex, remaining_seconds: SECONDS_PER_QUESTION }
    return current
  })

  return { getCurrent: () => current }
}

async function renderLanding(level: AssessmentLevelSummary = assessmentLevel) {
  vi.mocked(levelAssessmentsApi.fetchMyAssessmentLevel).mockResolvedValue(buildStatus(level))
  render(
    <MemoryRouter>
      <LevelAssessmentPage />
    </MemoryRouter>,
  )
  await screen.findByRole('button', { name: START_BUTTON_NAME })
}

async function startAssessment(level: AssessmentLevelSummary = assessmentLevel, initialRemainingSeconds = SECONDS_PER_QUESTION) {
  vi.mocked(levelAssessmentsApi.fetchMyAssessmentLevel).mockResolvedValue(buildStatus(level))
  const backend = setupFakeAttemptBackend(buildAttempt({ remaining_seconds: initialRemainingSeconds }))

  render(
    <MemoryRouter>
      <LevelAssessmentPage />
    </MemoryRouter>,
  )
  fireEvent.click(await screen.findByRole('button', { name: START_BUTTON_NAME }))
  await screen.findByText('First question?')
  return backend
}

describe('LevelAssessmentPage landing screen', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('describes per-question timing exactly, shows the instructions, and has not started any timer yet', async () => {
    await renderLanding(assessmentLevel)

    expect(
      screen.getByText(
        `You will have ${SECONDS_PER_QUESTION} seconds to answer each question; once time runs out on a ` +
          'question, it will lock and be marked as unanswered.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Before You Begin')).toBeInTheDocument()
    expect(screen.getByText(/independently, without help from colleagues/)).toBeInTheDocument()
    expect(screen.getByText(/No reference materials or notes/)).toBeInTheDocument()
    expect(screen.getByText(/No search engines or AI tools/)).toBeInTheDocument()
    expect(screen.getByText(/stable internet connection/)).toBeInTheDocument()
    expect(screen.getByText(/evidence of your training and competency/)).toBeInTheDocument()

    // No countdown of either shape is rendered before the learner confirms.
    expect(screen.queryByText(/^\d+s$/)).not.toBeInTheDocument()
    expect(screen.queryByText(/remaining/)).not.toBeInTheDocument()
  })

  it('describes fixed-total timing exactly instead, when the organization is configured that way', async () => {
    await renderLanding(fixedTotalAssessmentLevel)

    expect(
      screen.getByText(
        `You will have ${fixedTotalAssessmentLevel.total_exam_minutes} minutes for the entire exam; if time runs ` +
          'out before you finish, the exam will submit automatically with your answers so far, and any ' +
          'unanswered questions will be marked as zero.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/remaining/)).not.toBeInTheDocument()
  })

  it('shows the landing screen first (not the question directly) when resuming an already-open attempt, then resumes on confirmation', async () => {
    const openAttempt = buildAttempt()
    vi.mocked(levelAssessmentsApi.fetchMyAssessmentLevel).mockResolvedValue(
      buildStatus(assessmentLevel, { status: 'IN_PROGRESS', open_attempt_id: openAttempt.id }),
    )
    vi.mocked(levelAssessmentsApi.fetchLevelAssessmentAttempt).mockResolvedValue(openAttempt)

    render(
      <MemoryRouter>
        <LevelAssessmentPage />
      </MemoryRouter>,
    )

    // Landing/declaration screen first — not dropped straight into the
    // question — with resume-specific wording (via the button label), not
    // the fresh-start one.
    const resumeButton = await screen.findByRole('button', { name: CONTINUE_BUTTON_NAME })
    expect(screen.queryByText('First question?')).not.toBeInTheDocument()
    expect(screen.getByText('Before You Begin')).toBeInTheDocument()
    expect(levelAssessmentsApi.startLevelAssessmentAttempt).not.toHaveBeenCalled()

    fireEvent.click(resumeButton)
    await screen.findByText('First question?')

    // Resumed the existing attempt (fetched by id), never started a new one.
    expect(levelAssessmentsApi.fetchLevelAssessmentAttempt).toHaveBeenCalledWith(openAttempt.id)
    expect(levelAssessmentsApi.startLevelAssessmentAttempt).not.toHaveBeenCalled()
  })

  it('resumes at the correct question with the prefilled answer and correctly reduced time, not a fresh attempt', async () => {
    // Simulates what the backend's own away-time catch-up would return after
    // a browser crash/closure mid-exam: parked on question 2 (index 1) with
    // question 1's answer already saved, and only 42s left in this segment —
    // not the full per-question allocation.
    const resumedAttempt = buildAttempt({
      current_question_index: 1,
      answers_so_far: { '1': [10] },
      remaining_seconds: 42,
    })
    vi.mocked(levelAssessmentsApi.fetchMyAssessmentLevel).mockResolvedValue(
      buildStatus(assessmentLevel, { status: 'IN_PROGRESS', open_attempt_id: resumedAttempt.id }),
    )
    vi.mocked(levelAssessmentsApi.fetchLevelAssessmentAttempt).mockResolvedValue(resumedAttempt)

    render(
      <MemoryRouter>
        <LevelAssessmentPage />
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('button', { name: CONTINUE_BUTTON_NAME }))

    // Same attempt, resumed at the correct (second) question — not restarted.
    await screen.findByText('Second question?')
    expect(screen.queryByText('First question?')).not.toBeInTheDocument()
    expect(levelAssessmentsApi.startLevelAssessmentAttempt).not.toHaveBeenCalled()

    // Correctly reduced remaining time, not a fresh full countdown.
    await waitFor(() => expect(screen.getByText('42s')).toBeInTheDocument())
  })

  it('disables starting when the configured attempt cap is already exhausted, with a clear message', async () => {
    vi.mocked(levelAssessmentsApi.fetchMyAssessmentLevel).mockResolvedValue(
      buildStatus(assessmentLevel, { status: 'FAILED', attempts_remaining: 0 }),
    )
    render(
      <MemoryRouter>
        <LevelAssessmentPage />
      </MemoryRouter>,
    )

    const button = await screen.findByRole('button', { name: START_BUTTON_NAME })
    expect(button).toBeDisabled()
    expect(screen.getByText(/reached the maximum number of attempts/i)).toBeInTheDocument()

    fireEvent.click(button)
    expect(levelAssessmentsApi.startLevelAssessmentAttempt).not.toHaveBeenCalled()
  })
})

describe('LevelAssessmentPage PER_QUESTION sequential flow', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows one question at a time, with no back/skip control, and gates Next on answering', async () => {
    const backend = await startAssessment()

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

    // The server was told to advance (not just local state) — needed for
    // resume to work correctly after this point.
    expect(levelAssessmentsApi.advanceLevelAssessmentAttempt).toHaveBeenCalledWith(500, 1)
    expect(backend.getCurrent().current_question_index).toBe(1)
  })

  it(
    'continues depleting the countdown after the question is answered',
    async () => {
      await startAssessment()

      // Polled rather than checked instantly: the reset effect that sets
      // this to the full starting value commits in a render just after the
      // one "First question?" first appears in, so under load the two can
      // be observed a beat apart — harness overhead, not a product bug (see
      // the identical reasoning on the FIXED_TOTAL tests below).
      await waitFor(() => {
        expect(screen.getByText(`${SECONDS_PER_QUESTION}s`)).toBeInTheDocument()
      })

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
      const remainingWhenAnswered = Number(screen.getByText(/^\d+s$/).textContent!.replace('s', ''))

      // Selecting an answer only records/highlights it. It must not pause
      // the question's allocation while the learner waits to click Next.
      await waitFor(
        () => {
          const remaining = Number(screen.getByText(/^\d+s$/).textContent!.replace('s', ''))
          expect(remaining).toBeLessThan(remainingWhenAnswered)
        },
        { timeout: 2500 },
      )
    },
    (SECONDS_PER_QUESTION + 5) * 1000,
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

function parseRemainingSeconds(text: string): number {
  const match = text.match(/^(\d+):(\d+) remaining$/)
  if (!match) throw new Error(`Could not parse remaining time from "${text}"`)
  return Number(match[1]) * 60 + Number(match[2])
}

describe('LevelAssessmentPage FIXED_TOTAL exam-wide flow', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it(
    'shows one overall countdown that persists across questions instead of resetting',
    async () => {
      await startAssessment(fixedTotalAssessmentLevel, TOTAL_EXAM_SECONDS)

      // The whole-exam readout, not the per-question style ("Xs") — and not
      // stuck at zero (which the auto-submit race this mode is prone to on
      // mount would produce immediately and permanently). Polled with a
      // little retry budget rather than checked instantly: harness overhead
      // between the render and this check is expected and fine, a countdown
      // that never shows anything above zero is the actual regression.
      let atStart = 0
      await waitFor(() => {
        atStart = parseRemainingSeconds(screen.getByText(/remaining/).textContent!)
        expect(atStart).toBeGreaterThan(0)
      })
      expect(screen.queryByText(/^\d+s$/)).not.toBeInTheDocument()

      // Let it tick down for real before advancing.
      await waitFor(
        () => expect(parseRemainingSeconds(screen.getByText(/remaining/).textContent!)).toBeLessThan(atStart),
        { timeout: TOTAL_EXAM_SECONDS * 1000 },
      )
      const beforeAdvance = parseRemainingSeconds(screen.getByText(/remaining/).textContent!)
      expect(beforeAdvance).toBeLessThan(TOTAL_EXAM_SECONDS)

      fireEvent.click(screen.getByLabelText('Choice A'))
      fireEvent.click(screen.getByRole('button', { name: 'Next' }))
      await screen.findByText('Second question?')

      // Still counting from close to where it left off on question 1 —
      // monotonically at or below where it was, and nowhere near a reset
      // back to the full starting value, which a per-question reset bug
      // would produce.
      const afterAdvance = parseRemainingSeconds(screen.getByText(/remaining/).textContent!)
      expect(afterAdvance).toBeLessThanOrEqual(beforeAdvance)
      expect(afterAdvance).toBeGreaterThan(0)
      expect(afterAdvance).toBeLessThan(TOTAL_EXAM_SECONDS)
    },
    (TOTAL_EXAM_SECONDS + 8) * 1000,
  )

  it(
    'auto-submits with zero marks for every unanswered question once the overall timer reaches zero',
    async () => {
      const submitted: LevelAssessmentAttempt = {
        ...buildAttempt(),
        submitted_at: '2026-01-01T00:05:00Z',
        passed: false,
        score_percent: '0.00',
      }
      vi.mocked(levelAssessmentsApi.submitLevelAssessmentAttempt).mockResolvedValue(submitted)

      await startAssessment(fixedTotalAssessmentLevel, TOTAL_EXAM_SECONDS)

      // Never answer anything — let the whole-exam timer run out for real.
      // There is no per-question lock message in this mode; only the
      // overall timer reaching zero triggers the auto-submit.
      await waitFor(
        () => expect(levelAssessmentsApi.submitLevelAssessmentAttempt).toHaveBeenCalled(),
        { timeout: (TOTAL_EXAM_SECONDS + 3) * 1000 },
      )

      const [, payload] = vi.mocked(levelAssessmentsApi.submitLevelAssessmentAttempt).mock.calls[0]
      expect(payload).toEqual([
        { question: 1, selected_choices: [] },
        { question: 2, selected_choices: [] },
      ])

      await screen.findByText(/exam time ran out/i)
    },
    (TOTAL_EXAM_SECONDS + 8) * 1000,
  )
})
