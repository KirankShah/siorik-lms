import { useEffect, useState } from 'react'
import { ClipboardList } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { fetchQuizForSlide } from '../../lib/quizApi'
import type { QuizDetail } from '../../types/quiz'

export function QuizSummaryPreview({ slideId }: { slideId: number }) {
  const [quiz, setQuiz] = useState<QuizDetail | null | undefined>(undefined)

  useEffect(() => {
    setQuiz(undefined)
    fetchQuizForSlide(slideId)
      .then(setQuiz)
      .catch(() => setQuiz(null))
  }, [slideId])

  if (quiz === undefined) return <p className="text-sm text-neutral-500">Loading…</p>

  if (!quiz) {
    return (
      <div className="flex items-center gap-2 text-sm text-neutral-400">
        <ClipboardList className="h-4 w-4" />
        No quiz yet — click edit to create one.
      </div>
    )
  }

  return (
    <div>
      <p className="text-sm font-medium text-neutral-900">{quiz.title}</p>
      <div className="mt-1.5 flex flex-wrap gap-2">
        <Badge variant="navy">
          {quiz.questions.length} question{quiz.questions.length === 1 ? '' : 's'}
        </Badge>
        <Badge>{quiz.pass_percentage}% to pass</Badge>
        {quiz.max_attempts !== null && (
          <Badge>
            {quiz.max_attempts} attempt{quiz.max_attempts === 1 ? '' : 's'} max
          </Badge>
        )}
        {quiz.time_limit_minutes !== null && <Badge>{quiz.time_limit_minutes} min limit</Badge>}
      </div>
    </div>
  )
}
