import { useEffect, useState } from 'react'
import { QuizPlayer } from '../QuizPlayer'
import { savePageProgress } from '../../lib/coursesApi'
import { fetchQuizForPage } from '../../lib/quizApi'
import type { Enrollment, PageProgress, PageSummary } from '../../types/courses'
import type { QuizDetail } from '../../types/quiz'
import { PageNavFooter } from './PageNavFooter'

interface QuizPagePlayerProps {
  page: PageSummary
  courseId: number
  enrollmentId: number
  existingProgress: PageProgress | undefined
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  onProgressSynced: (enrollment: Enrollment) => void
}

export function QuizPagePlayer({
  page,
  courseId,
  enrollmentId,
  existingProgress,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onProgressSynced,
}: QuizPagePlayerProps) {
  const [quiz, setQuiz] = useState<QuizDetail | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchQuizForPage(page.id)
      .then(setQuiz)
      .catch(() => setError('Could not load this quiz.'))
  }, [page.id])

  async function markComplete() {
    if (existingProgress?.completed_at) return
    try {
      const enrollment = await savePageProgress(enrollmentId, { page: page.id, completed: true })
      onProgressSynced(enrollment)
    } catch {
      // Progress tracking failing shouldn't block the learner from moving on —
      // the quiz attempt itself is already recorded server-side regardless.
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (quiz === undefined) return <p className="text-sm text-slate-500">Loading quiz…</p>
  if (quiz === null) return <p className="text-sm text-slate-400 italic">This quiz hasn't been set up yet.</p>

  return (
    <div>
      <QuizPlayer quizSummary={quiz} courseId={courseId} onSubmitted={() => void markComplete()} />
      <PageNavFooter hasPrevious={hasPrevious} hasNext={hasNext} onPrevious={onPrevious} onNext={onNext} />
    </div>
  )
}
