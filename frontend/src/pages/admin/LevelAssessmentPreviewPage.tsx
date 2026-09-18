import { useEffect, useState } from 'react'
import { Check, X } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { previewLevelAssessment } from '../../lib/levelAssessmentsApi'
import type { LevelAssessmentPreview } from '../../types/levelAssessments'

const OPTION_LETTERS: Array<'A' | 'B' | 'C' | 'D' | 'E'> = ['A', 'B', 'C', 'D', 'E']

// Admin-only content-review surface: shows what one real attempt at this
// level would draw (same random sample, same one-question-per-screen shape
// the real exam uses), but freely navigable both ways, no timer, and the
// answer key visible immediately — nothing here is backed by a
// LevelAssessmentAttempt, so it never touches attempt counts or reporting.
export function LevelAssessmentPreviewPage() {
  const { levelId } = useParams<{ levelId: string }>()
  const [preview, setPreview] = useState<LevelAssessmentPreview | null>(null)
  const [index, setIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!levelId) return
    setPreview(null)
    setIndex(0)
    setError(null)
    previewLevelAssessment(Number(levelId))
      .then(setPreview)
      .catch(() => setError('Could not draw a preview for this level — check that its question pool is large enough.'))
  }, [levelId])

  function redraw() {
    if (!levelId) return
    setPreview(null)
    setIndex(0)
    setError(null)
    previewLevelAssessment(Number(levelId))
      .then(setPreview)
      .catch(() => setError('Could not draw a preview for this level — check that its question pool is large enough.'))
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <p className="text-sm text-red-600">{error}</p>
        <Link to="/admin/assessment-questions" className="mt-2 inline-block text-sm text-brand-navy underline">
          Back to Level Assessments
        </Link>
      </div>
    )
  }

  if (!preview) {
    return <p className="mx-auto max-w-2xl text-sm text-neutral-500">Drawing a preview…</p>
  }

  const question = preview.questions[index]
  const correctSet = new Set(question.correct_answers)

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-neutral-900">
            {preview.assessment_level.name_display} Assessment — Preview
          </h1>
          <p className="mt-1 text-xs text-neutral-500">
            Freely navigable, no timer, and correct answers are shown — this never records an attempt.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={redraw}>
          Draw again
        </Button>
      </div>

      <Card className="mt-4">
        <div className="flex items-center justify-between gap-4">
          <span className="text-xs font-medium text-neutral-400">
            Question {index + 1} of {preview.questions.length}
          </span>
          <span className="text-xs font-normal text-neutral-400">
            {question.marks} {question.marks === 1 ? 'mark' : 'marks'}
          </span>
        </div>

        <div
          className="mt-3 text-sm font-medium text-neutral-900 [overflow-wrap:anywhere]"
          dangerouslySetInnerHTML={{ __html: question.question_text }}
        />

        <ul className="mt-4 space-y-2">
          {OPTION_LETTERS.filter((letter) => question.options[letter]).map((letter) => {
            const isCorrect = correctSet.has(letter)
            return (
              <li
                key={letter}
                className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
                  isCorrect ? 'border-emerald-300 bg-emerald-50 text-emerald-800' : 'border-neutral-200 text-neutral-700'
                }`}
              >
                {isCorrect ? (
                  <Check className="h-4 w-4 shrink-0 text-emerald-600" />
                ) : (
                  <X className="h-4 w-4 shrink-0 text-neutral-300" />
                )}
                <span className="font-medium">{letter}.</span> {question.options[letter]}
              </li>
            )
          })}
        </ul>

        {question.explanation && (
          <p className="mt-4 rounded-md bg-neutral-50 px-3 py-2 text-sm text-neutral-600">{question.explanation}</p>
        )}

        <div className="mt-6 flex items-center justify-between">
          <Button variant="secondary" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
            Previous
          </Button>
          <Button disabled={index === preview.questions.length - 1} onClick={() => setIndex((i) => i + 1)}>
            Next
          </Button>
        </div>
      </Card>
    </div>
  )
}
