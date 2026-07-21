import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { QuestionEditor } from '../../components/admin/QuestionEditor'
import { createQuestion, fetchQuizDetail, updateQuiz } from '../../lib/quizApi'
import type { QuizDetail } from '../../types/quiz'

export function QuizEditorPage() {
  const { slug, quizId } = useParams<{ slug: string; quizId: string }>()
  const [quiz, setQuiz] = useState<QuizDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [passPercentage, setPassPercentage] = useState(70)
  const [timeLimitMinutes, setTimeLimitMinutes] = useState<number | ''>('')
  const [maxAttempts, setMaxAttempts] = useState<number | ''>('')
  const [randomizeQuestions, setRandomizeQuestions] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const [isAddingQuestion, setIsAddingQuestion] = useState(false)
  const [newQuestionText, setNewQuestionText] = useState('')

  function loadQuiz() {
    if (!quizId) return
    fetchQuizDetail(Number(quizId))
      .then((detail) => {
        setQuiz(detail)
        setTitle(detail.title)
        setPassPercentage(detail.pass_percentage)
        setTimeLimitMinutes(detail.time_limit_minutes ?? '')
        setMaxAttempts(detail.max_attempts ?? '')
        setRandomizeQuestions(detail.randomize_questions)
      })
      .catch(() => setError('Could not load this quiz.'))
  }

  useEffect(loadQuiz, [quizId])

  async function handleSaveSettings(event: FormEvent) {
    event.preventDefault()
    if (!quiz) return
    setIsSaving(true)
    setSaveSuccess(false)
    try {
      await updateQuiz(quiz.id, {
        title,
        pass_percentage: passPercentage,
        time_limit_minutes: timeLimitMinutes === '' ? null : Number(timeLimitMinutes),
        max_attempts: maxAttempts === '' ? null : Number(maxAttempts),
        randomize_questions: randomizeQuestions,
      })
      setSaveSuccess(true)
      loadQuiz()
    } catch {
      setError('Could not save quiz settings.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleAddQuestion() {
    if (!quiz || !newQuestionText.trim()) return
    try {
      await createQuestion({
        quiz: quiz.id,
        question_text: newQuestionText,
        question_type: 'SINGLE_CHOICE',
        order: quiz.questions.length + 1,
        points: 1,
      })
      setNewQuestionText('')
      setIsAddingQuestion(false)
      loadQuiz()
    } catch {
      setError('Could not add question.')
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!quiz) return <p className="text-sm text-slate-500">Loading quiz…</p>

  return (
    <div className="space-y-6">
      <Link to={`/admin/courses/${slug}/edit`} className="text-sm text-slate-600 hover:underline">
        ← Back to course
      </Link>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Quiz Settings</h1>
        <form onSubmit={handleSaveSettings} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Title</label>
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">Pass %</label>
              <input
                type="number"
                min={0}
                max={100}
                value={passPercentage}
                onChange={(e) => setPassPercentage(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Time limit (min)</label>
              <input
                type="number"
                value={timeLimitMinutes}
                onChange={(e) => setTimeLimitMinutes(e.target.value === '' ? '' : Number(e.target.value))}
                placeholder="No limit"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Max attempts</label>
              <input
                type="number"
                value={maxAttempts}
                onChange={(e) => setMaxAttempts(e.target.value === '' ? '' : Number(e.target.value))}
                placeholder="Unlimited"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={randomizeQuestions}
              onChange={(e) => setRandomizeQuestions(e.target.checked)}
            />
            Randomize question order
          </label>

          {saveSuccess && <p className="text-sm text-emerald-600">Saved.</p>}

          <button
            type="submit"
            disabled={isSaving}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:opacity-60"
          >
            {isSaving ? 'Saving…' : 'Save Settings'}
          </button>
        </form>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Questions</h2>
        <div className="mt-4 space-y-4">
          {quiz.questions.map((question, index) => (
            <QuestionEditor key={question.id} question={question} index={index} onChanged={loadQuiz} />
          ))}
        </div>

        {isAddingQuestion ? (
          <div className="mt-4 flex items-center gap-2">
            <input
              value={newQuestionText}
              onChange={(e) => setNewQuestionText(e.target.value)}
              placeholder="Question text"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button type="button" onClick={handleAddQuestion} className="text-sm font-medium text-emerald-700">
              Add
            </button>
            <button type="button" onClick={() => setIsAddingQuestion(false)} className="text-sm text-slate-500">
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsAddingQuestion(true)}
            className="mt-4 text-sm font-medium text-slate-900 hover:underline"
          >
            + Add question
          </button>
        )}
      </div>
    </div>
  )
}
