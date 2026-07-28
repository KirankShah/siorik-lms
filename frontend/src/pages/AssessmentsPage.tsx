import { useEffect, useState } from 'react'
import { ClipboardList } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { useAuth } from '../context/AuthContext'
import { fetchQuizzes } from '../lib/quizApi'
import { isAdminRole } from '../lib/roles'
import type { QuizListItem } from '../types/quiz'

export function AssessmentsPage() {
  const { user } = useAuth()
  const [quizzes, setQuizzes] = useState<QuizListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchQuizzes()
      .then(setQuizzes)
      .catch(() => setError('Could not load assessments.'))
  }, [])

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (!quizzes) {
    return <p className="text-sm text-neutral-500">Loading assessments…</p>
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Assessments</h1>

      {quizzes.length === 0 ? (
        <Card className="mt-6 flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-navy/10 text-brand-navy">
            <ClipboardList className="h-6 w-6" />
          </div>
          <p className="text-sm font-medium text-neutral-900">No assessments yet</p>
          <p className="max-w-sm text-sm text-neutral-500">
            {isAdminRole(user?.role)
              ? "Exams live inside a course's content — create a course, then add a quiz to one of its slides."
              : "There's nothing to take yet — check back once your instructor adds a quiz."}
          </p>
          {isAdminRole(user?.role) && (
            <Link
              to="/admin/courses"
              className="mt-2 inline-flex items-center rounded-md bg-brand-navy px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-navy-light"
            >
              Create your first Exam
            </Link>
          )}
        </Card>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {quizzes.map((quiz) => (
            <Card key={quiz.id}>
              <p className="text-sm font-semibold text-neutral-900">{quiz.title}</p>
              <div className="mt-3 flex flex-wrap gap-2">
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
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
