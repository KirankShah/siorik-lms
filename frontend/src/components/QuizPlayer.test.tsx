import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QuizPlayer } from './QuizPlayer'
import * as quizApi from '../lib/quizApi'
import type { QuizAttemptResult, QuizDetail, QuizSummary } from '../types/quiz'

vi.mock('../lib/quizApi')
vi.mock('../lib/certificatesApi')

const quizSummary: QuizSummary = {
  id: 1,
  title: 'Money Laundering Basics',
  pass_percentage: 70,
  time_limit_minutes: null,
  max_attempts: null,
}

const quizDetail: QuizDetail = {
  ...quizSummary,
  slide: 10,
  randomize_questions: false,
  questions: [
    {
      id: 100,
      question_text: 'Which stage is this?',
      question_type: 'SINGLE_CHOICE',
      order: 1,
      points: 1,
      image: null,
      video_url: null,
      marks: 1,
      choices: [
        { id: 1000, choice_text: 'Placement', order: 1 },
        { id: 1001, choice_text: 'Layering', order: 2 },
      ],
      buckets: [],
      categorize_items: [],
      hotspot_regions: [],
      word_bank_tokens: [],
    },
  ],
}

// A long, unbroken run of characters — the exact shape of text that overflows
// a fixed-width container unless overflow-wrap is set, since there are no
// natural break points (spaces) for the browser to wrap on.
const LONG_UNBROKEN_EXPLANATION =
  'Theseareexamplesofsectorsthatarespecificallytargetedbycriminalsseekingtolaunderillegallyobtainedfundsthroughlegitimatelookingbusinesschannelsandtransactions'.repeat(3)

function buildResult(overrides: Partial<QuizAttemptResult['answers'][number]> = {}): QuizAttemptResult {
  return {
    id: 500,
    user: 1,
    quiz: quizDetail.id,
    started_at: '2026-08-01T00:00:00Z',
    submitted_at: '2026-08-01T00:05:00Z',
    score_percent: '100.00',
    passed: true,
    attempt_number: 1,
    answers: [
      {
        id: 900,
        question: 100,
        selected_choices: [1000],
        category_placements: {},
        selected_regions: [],
        fill_blank_text: {},
        word_bank_placements: {},
        is_correct: true,
        correct_choice_ids: [1000],
        correct_order: null,
        correct_placements: null,
        correct_region_ids: [],
        correct_fill_blank_text: null,
        correct_word_bank_placements: null,
        explanation: LONG_UNBROKEN_EXPLANATION,
        feedback_correct: LONG_UNBROKEN_EXPLANATION,
        feedback_incorrect: '',
        ...overrides,
      },
    ],
  }
}

async function submitQuiz(result: QuizAttemptResult) {
  vi.mocked(quizApi.fetchQuizDetail).mockResolvedValue(quizDetail)
  vi.mocked(quizApi.submitQuizAttempt).mockResolvedValue(result)

  render(<QuizPlayer quizSummary={quizSummary} />)

  fireEvent.click(screen.getByRole('button', { name: 'Start Quiz' }))
  await waitFor(() => expect(screen.getByText('Submit')).toBeInTheDocument())

  fireEvent.click(screen.getByLabelText('Placement'))
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }))

  await waitFor(() => expect(screen.getByText(/pass mark/)).toBeInTheDocument())
}

describe('QuizPlayer results feedback text wrapping', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('applies overflow-wrap to a long unbroken explanation instead of letting it overflow', async () => {
    await submitQuiz(buildResult())

    const explanation = screen.getByText(LONG_UNBROKEN_EXPLANATION, { selector: 'div' })
    expect(explanation.className).toMatch(/overflow-wrap:anywhere/)
    expect(explanation.className).toContain('min-w-0')
    expect(explanation.className).not.toMatch(/whitespace-nowrap/)
  })

  it('applies wrapping to correct-answer feedback text', async () => {
    await submitQuiz(buildResult({ feedback_correct: LONG_UNBROKEN_EXPLANATION, is_correct: true }))

    const feedback = screen.getByText(LONG_UNBROKEN_EXPLANATION, { selector: 'p' })
    expect(feedback.className).toMatch(/break-words|overflow-wrap/)
    expect(feedback.className).not.toMatch(/whitespace-nowrap/)
  })

  it('applies wrapping to incorrect-answer feedback text', async () => {
    await submitQuiz(
      buildResult({
        is_correct: false,
        feedback_correct: '',
        feedback_incorrect: LONG_UNBROKEN_EXPLANATION,
        correct_choice_ids: [1001],
      }),
    )

    const feedback = screen.getByText(LONG_UNBROKEN_EXPLANATION, { selector: 'p' })
    expect(feedback.className).toMatch(/break-words|overflow-wrap/)
    expect(feedback.className).not.toMatch(/whitespace-nowrap/)
  })

  it('still renders correctly for short feedback text', async () => {
    await submitQuiz(buildResult({ explanation: 'Correct — well done.', feedback_correct: 'Nice work.' }))

    expect(screen.getByText('Correct — well done.')).toBeInTheDocument()
    expect(screen.getByText('Nice work.')).toBeInTheDocument()
  })
})

describe('QuizPlayer results screen has no inline retake/certificate actions', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('does not render Retake Quiz or Download Certificate when the attempt passed', async () => {
    await submitQuiz(buildResult({ }))

    expect(screen.queryByText('Retake Quiz')).not.toBeInTheDocument()
    expect(screen.queryByText('Download Certificate')).not.toBeInTheDocument()
  })

  it('does not render Retake Quiz or Download Certificate when the attempt failed', async () => {
    const failingResult = buildResult({ is_correct: false, feedback_correct: '', correct_choice_ids: [1001] })
    failingResult.passed = false
    failingResult.score_percent = '0.00'

    await submitQuiz(failingResult)

    expect(screen.queryByText('Retake Quiz')).not.toBeInTheDocument()
    expect(screen.queryByText('Download Certificate')).not.toBeInTheDocument()
  })
})
