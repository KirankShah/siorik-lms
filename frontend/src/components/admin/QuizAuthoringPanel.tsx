import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { createQuestion, createQuiz, fetchQuizForPage, updateQuiz } from '../../lib/quizApi'
import type { QuizDetail } from '../../types/quiz'
import { QuestionForm } from './QuestionForm'

interface QuizAuthoringPanelProps {
  pageId: number
  pageTitle: string
}

export function QuizAuthoringPanel({ pageId, pageTitle }: QuizAuthoringPanelProps) {
  const [quiz, setQuiz] = useState<QuizDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setIsLoading(true)
    fetchQuizForPage(pageId)
      .then(setQuiz)
      .catch(() => setError('Could not load this quiz.'))
      .finally(() => setIsLoading(false))
  }

  useEffect(load, [pageId])

  async function handleCreateQuiz() {
    try {
      await createQuiz({
        page: pageId,
        title: pageTitle,
        pass_percentage: 70,
        time_limit_minutes: null,
        max_attempts: null,
        randomize_questions: false,
      })
      load()
    } catch {
      setError('Could not create quiz.')
    }
  }

  if (isLoading) return <p className="text-sm text-slate-500">Loading quiz…</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>

  if (!quiz) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center">
        <p className="text-sm text-slate-500">This page doesn't have a quiz yet.</p>
        <button
          type="button"
          onClick={() => void handleCreateQuiz()}
          className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
        >
          Create quiz
        </button>
      </div>
    )
  }

  return <QuizEditor quiz={quiz} onChanged={load} />
}

function QuizEditor({ quiz, onChanged }: { quiz: QuizDetail; onChanged: () => void }) {
  const [title, setTitle] = useState(quiz.title)
  const [passPercentage, setPassPercentage] = useState(quiz.pass_percentage)
  const [timeLimitMinutes, setTimeLimitMinutes] = useState<number | ''>(quiz.time_limit_minutes ?? '')
  const [maxAttempts, setMaxAttempts] = useState<number | ''>(quiz.max_attempts ?? '')
  const [randomizeQuestions, setRandomizeQuestions] = useState(quiz.randomize_questions)
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [isAddingQuestion, setIsAddingQuestion] = useState(false)
  const [newQuestionText, setNewQuestionText] = useState('')

  async function handleSaveSettings(event: FormEvent) {
    event.preventDefault()
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
      onChanged()
    } catch {
      setError('Could not save quiz settings.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleAddQuestion() {
    if (!newQuestionText.trim()) return
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
      onChanged()
    } catch {
      setError('Could not add question.')
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSaveSettings} className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-900">Quiz Settings</h2>
        <div>
          <label className="block text-xs font-medium text-slate-700">Title</label>
          <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-700">Pass %</label>
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
            <label className="block text-xs font-medium text-slate-700">Time limit (min)</label>
            <input
              type="number"
              value={timeLimitMinutes}
              onChange={(e) => setTimeLimitMinutes(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="No limit"
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-700">Max attempts</label>
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
          <input type="checkbox" checked={randomizeQuestions} onChange={(e) => setRandomizeQuestions(e.target.checked)} />
          Randomize question order
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {saveSuccess && <p className="text-sm text-emerald-600">Saved.</p>}

        <button
          type="submit"
          disabled={isSaving}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {isSaving ? 'Saving…' : 'Save Settings'}
        </button>
      </form>

      <div className="border-t border-slate-200 pt-4">
        <h2 className="text-sm font-semibold text-slate-900">Questions</h2>
        <div className="mt-4 space-y-4">
          {quiz.questions.map((question, index) => (
            <QuestionForm key={question.id} question={question} index={index} onChanged={onChanged} />
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
            <button type="button" onClick={() => void handleAddQuestion()} className="text-sm font-medium text-emerald-700">
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
