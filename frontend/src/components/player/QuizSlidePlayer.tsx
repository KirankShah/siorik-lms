import { useEffect, useState } from 'react'
import { QuizPlayer } from '../QuizPlayer'
import { fetchQuizForSlide } from '../../lib/quizApi'
import type { QuizDetail } from '../../types/quiz'
import type { SlideSummary } from '../../types/slides'

interface QuizSlidePlayerProps {
  slide: SlideSummary
  onSubmitted: () => void
}

export function QuizSlidePlayer({ slide, onSubmitted }: QuizSlidePlayerProps) {
  const [quiz, setQuiz] = useState<QuizDetail | null | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setQuiz(undefined)
    fetchQuizForSlide(slide.id)
      .then(setQuiz)
      .catch(() => setError('Could not load this quiz.'))
  }, [slide.id])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (quiz === undefined) return <p className="text-sm text-neutral-500">Loading quiz…</p>
  if (quiz === null) return <p className="text-sm text-neutral-400 italic">This quiz hasn't been set up yet.</p>

  return <QuizPlayer quizSummary={quiz} onSubmitted={onSubmitted} />
}
