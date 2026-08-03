import type { ReactNode } from 'react'
import { splitBlankSegments } from '../lib/fillBlankMarkup'

interface FillBlankSentenceProps {
  questionText: string
  renderBlank: (blankIndex: number) => ReactNode
}

// Single shared substitution point for every FILL_BLANK renderer (quiz-taking
// input, quiz-taking word bank, the post-submission review, and the admin
// authoring preview) — splits the question text on {{N}} once and lets each
// caller supply what belongs in each blank's place, so the {{N}} splitting
// logic never needs reimplementing per screen.
export function FillBlankSentence({ questionText, renderBlank }: FillBlankSentenceProps) {
  return (
    <>
      {splitBlankSegments(questionText).map((segment, i) =>
        typeof segment === 'number' ? <span key={i}>{renderBlank(segment)}</span> : <span key={i}>{segment}</span>,
      )}
    </>
  )
}
