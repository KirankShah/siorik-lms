import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SlidePlayer } from './SlidePlayer'
import { SlideNavFooter } from './SlideNavFooter'
import * as coursesApi from '../../lib/coursesApi'
import * as quizApi from '../../lib/quizApi'
import * as scenariosApi from '../../lib/scenariosApi'
import * as slidesApi from '../../lib/slidesApi'
import type { Enrollment } from '../../types/courses'
import type { QuizDetail } from '../../types/quiz'
import type { ScenarioNode } from '../../types/scenarios'
import type { SlideElement, SlideSummary } from '../../types/slides'

vi.mock('../../lib/coursesApi')
vi.mock('../../lib/quizApi')
vi.mock('../../lib/scenariosApi')
vi.mock('../../lib/slidesApi')
vi.mock('../../lib/slideTemplatesApi')

const baseSlide: Omit<SlideSummary, 'slide_type'> = {
  id: 1,
  title: 'Slide',
  order: 1,
  layout: 'STACKED',
  image_column_width: 'STANDARD',
  template_override: null,
  estimated_minutes: 0,
}

function makeEnrollment(): Enrollment {
  return {
    id: 1,
    user: 1,
    course: 1,
    enrolled_at: '2026-08-01T00:00:00Z',
    completed_at: null,
    status: 'IN_PROGRESS',
    progress_percent: 0,
    completed_lesson_ids: [],
    slide_progress: [],
    certificate_ineligible_reason: null,
  }
}

// Mirrors how CourseDetailPage wires SlidePlayer's onCanAdvanceChange into
// SlideNavFooter's disabled/tooltip props — the thing under test is whether
// this whole chain unlocks Next only after a genuine submission.
function Harness({ slide }: { slide: SlideSummary }) {
  const [canAdvance, setCanAdvance] = useState(false)
  const [reason, setReason] = useState<string | undefined>(undefined)
  return (
    <>
      <SlidePlayer
        slide={slide}
        courseTemplateId={null}
        enrollmentId={1}
        existingProgress={undefined}
        onProgressSynced={() => {}}
        onCanAdvanceChange={(advance, _seconds, disabledReason) => {
          setCanAdvance(advance)
          setReason(disabledReason)
        }}
      />
      <SlideNavFooter
        hasPrevious={false}
        hasNext={true}
        onPrevious={() => {}}
        onNext={() => {}}
        nextDisabled={!canAdvance}
        nextDisabledReason={reason}
      />
    </>
  )
}

describe('Next-button gating on QUIZ and SCENARIO slides', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(coursesApi.saveSlideProgress).mockResolvedValue(makeEnrollment())
  })

  it('blocks Next until the quiz is submitted, then unlocks it immediately', async () => {
    const quizSlide: SlideSummary = { ...baseSlide, slide_type: 'QUIZ' }
    const quizDetail: QuizDetail = {
      id: 5,
      title: 'Quiz',
      pass_percentage: 70,
      time_limit_minutes: null,
      max_attempts: null,
      slide: quizSlide.id,
      randomize_questions: false,
      questions: [
        {
          id: 50,
          question_text: 'Q1',
          question_type: 'SINGLE_CHOICE',
          order: 1,
          points: 1,
          image: null,
          video_url: null,
          marks: 1,
          choices: [
            { id: 500, choice_text: 'A', order: 1 },
            { id: 501, choice_text: 'B', order: 2 },
          ],
          buckets: [],
          categorize_items: [],
          hotspot_regions: [],
          word_bank_tokens: [],
        },
      ],
    }
    vi.mocked(quizApi.fetchQuizForSlide).mockResolvedValue(quizDetail)
    vi.mocked(quizApi.fetchQuizDetail).mockResolvedValue(quizDetail)
    vi.mocked(quizApi.submitQuizAttempt).mockResolvedValue({
      id: 900,
      user: 1,
      quiz: quizDetail.id,
      started_at: '2026-08-01T00:00:00Z',
      submitted_at: '2026-08-01T00:01:00Z',
      score_percent: '0.00',
      passed: false,
      attempt_number: 1,
      answers: [],
    })

    render(<Harness slide={quizSlide} />)

    const nextButton = await screen.findByRole('button', { name: /Next/ })
    expect(nextButton).toBeDisabled()
    expect(nextButton.closest('[title]')).toHaveAttribute('title', 'Submit your answer to continue.')

    fireEvent.click(await screen.findByRole('button', { name: 'Start Quiz' }))
    fireEvent.click(await screen.findByLabelText('A'))
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }))

    // Unlocks immediately on submission regardless of pass/fail.
    await waitFor(() => expect(screen.getByRole('button', { name: /Next/ })).toBeEnabled())
    expect(screen.getByRole('button', { name: /Next/ }).closest('[title]')).toBeNull()
  })

  it('blocks Next until a scenario reaches a terminal ending, then unlocks it immediately', async () => {
    const scenarioSlide: SlideSummary = { ...baseSlide, slide_type: 'SCENARIO' }
    const node: ScenarioNode = {
      id: 1,
      slide: scenarioSlide.id,
      node_key: 'start',
      prompt: 'What do you do?',
      prompt_image: null,
      is_start: true,
      choices: [
        { id: 10, node: 1, choice_text: 'Report it', next_node: null, feedback_text: '', order: 1 },
      ],
    }
    vi.mocked(scenariosApi.fetchScenarioNodesForSlide).mockResolvedValue([node])
    vi.mocked(scenariosApi.submitScenarioAttempt).mockResolvedValue({
      id: 1,
      enrollment: 1,
      slide: scenarioSlide.id,
      path_taken: [10],
      reached_recommended_ending: true,
      completed_at: '2026-08-01T00:00:00Z',
    })

    render(<Harness slide={scenarioSlide} />)

    const nextButton = await screen.findByRole('button', { name: /Next/ })
    expect(nextButton).toBeDisabled()
    expect(nextButton.closest('[title]')).toHaveAttribute('title', 'Reach an ending to continue.')

    fireEvent.click(await screen.findByRole('button', { name: 'Report it' }))

    await waitFor(() => expect(screen.getByRole('button', { name: /Next/ })).toBeEnabled())
  })
})

describe('Next-button gating on a CONTENT slide with a Dialogue element', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(coursesApi.saveSlideProgress).mockResolvedValue(makeEnrollment())
  })

  it('blocks Next until the dialogue reaches its final line, even though dwell time (estimated_minutes: 0) is already satisfied', async () => {
    const contentSlide: SlideSummary = { ...baseSlide, slide_type: 'CONTENT', estimated_minutes: 0 }
    const dialogueElement: SlideElement = {
      id: 1,
      slide: contentSlide.id,
      order: 1,
      element_type: 'DIALOGUE',
      rich_text: '',
      file: null,
      video_url: '',
      video_file: null,
      embed_url: '',
      caption: '',
      align: 'CENTER',
      dialogue_scene: 1,
      dialogue_character_left: null,
      dialogue_character_right: null,
      dialogue_lines: [
        { speaker: 'LEFT', text: 'Hi' },
        { speaker: 'RIGHT', text: 'Hello' },
      ],
      dialogue_scene_detail: { id: 1, name: 'Scene', scene_type: 'FRONT_OFFICE', background_image: 'http://x/scene.png' },
      dialogue_character_left_detail: null,
      dialogue_character_right_detail: null,
    }
    vi.mocked(slidesApi.fetchElements).mockResolvedValue([dialogueElement])

    render(<Harness slide={contentSlide} />)

    const nextButton = await screen.findByRole('button', { name: /Next/ })
    await waitFor(() => expect(nextButton).toBeDisabled())
    expect(nextButton.closest('[title]')).toHaveAttribute('title', 'Finish the conversation to continue.')

    const firstLine = await screen.findByText('Hi')
    fireEvent.click(firstLine.closest('button')!)

    // Exact-string match (not the loose /Next/ regex used elsewhere in this
    // file) — once the dialogue reaches its last line, its own completion
    // copy ("...use Next below to continue") also matches /Next/, making a
    // loose query ambiguous.
    const nextButtonAfter = await screen.findByRole('button', { name: 'Next →' })
    await waitFor(() => expect(nextButtonAfter).toBeEnabled())
    expect(nextButtonAfter.closest('[title]')).toBeNull()
  })

  it('never gates Next on a CONTENT slide with no Dialogue element (plain dwell-time gating only)', async () => {
    const contentSlide: SlideSummary = { ...baseSlide, slide_type: 'CONTENT', estimated_minutes: 0 }
    vi.mocked(slidesApi.fetchElements).mockResolvedValue([])

    render(<Harness slide={contentSlide} />)

    await waitFor(() => expect(screen.getByRole('button', { name: /Next/ })).toBeEnabled())
  })
})
