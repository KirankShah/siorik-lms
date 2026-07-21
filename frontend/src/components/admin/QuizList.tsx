import { useState } from 'react'
import { Link } from 'react-router-dom'
import { createQuiz } from '../../lib/quizApi'
import type { QuizSummary } from '../../types/quiz'

interface QuizListProps {
  courseId: number
  courseSlug: string
  quizzes: QuizSummary[]
  onChanged: () => void
}

export function QuizList({ courseId, courseSlug, quizzes, onChanged }: QuizListProps) {
  const [isCreating, setIsCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleCreate() {
    if (!title.trim()) return
    try {
      await createQuiz({
        course: courseId,
        title,
        pass_percentage: 70,
        time_limit_minutes: null,
        max_attempts: null,
        randomize_questions: false,
      })
      setTitle('')
      setIsCreating(false)
      onChanged()
    } catch {
      setError('Could not create quiz.')
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">Quizzes</h2>
      <ul className="mt-3 space-y-2">
        {quizzes.map((quiz) => (
          <li
            key={quiz.id}
            className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 text-sm"
          >
            <span>{quiz.title}</span>
            <Link to={`/admin/courses/${courseSlug}/quizzes/${quiz.id}`} className="text-slate-900 underline">
              Edit questions
            </Link>
          </li>
        ))}
        {quizzes.length === 0 && <li className="text-sm text-slate-400">No quizzes yet.</li>}
      </ul>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      {isCreating ? (
        <div className="mt-3 flex items-center gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Quiz title"
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <button type="button" onClick={handleCreate} className="text-sm font-medium text-emerald-700">
            Create
          </button>
          <button type="button" onClick={() => setIsCreating(false)} className="text-sm text-slate-500">
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setIsCreating(true)}
          className="mt-3 text-sm font-medium text-slate-900 hover:underline"
        >
          + New Quiz
        </button>
      )}
    </div>
  )
}
