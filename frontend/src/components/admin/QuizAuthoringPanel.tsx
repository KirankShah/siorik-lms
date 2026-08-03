import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { createQuestion, createQuiz, fetchQuizForSlide, updateQuiz } from '../../lib/quizApi'
import type { QuizDetail } from '../../types/quiz'
import { QuestionForm } from './QuestionForm'

interface QuizAuthoringPanelProps {
  slideId: number
  defaultTitle: string
}

export function QuizAuthoringPanel({ slideId, defaultTitle }: QuizAuthoringPanelProps) {
  const [quiz, setQuiz] = useState<QuizDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // showLoading is false for background refreshes triggered by edits further
  // down the tree (e.g. adding a Choice) — those must update `quiz` in place
  // without unmounting QuizEditor/QuestionForm, or their local edit state
  // (unsaved question type, isEditing, etc.) would be wiped on every save.
  function load(showLoading = true) {
    if (showLoading) setIsLoading(true)
    fetchQuizForSlide(slideId)
      .then(setQuiz)
      .catch(() => setError('Could not load this quiz.'))
      .finally(() => setIsLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(), [slideId])

  async function handleCreateQuiz() {
    try {
      await createQuiz({
        slide: slideId,
        title: defaultTitle,
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

  if (isLoading) return <p className="text-sm text-neutral-500">Loading quiz…</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>

  if (!quiz) {
    return (
      <div className="rounded-xl border border-dashed border-neutral-300 p-6 text-center">
        <p className="text-sm text-neutral-500">This slide doesn't have a quiz yet.</p>
        <Button size="sm" className="mt-3" onClick={() => void handleCreateQuiz()}>
          Create quiz
        </Button>
      </div>
    )
  }

  return <QuizEditor quiz={quiz} onChanged={() => load(false)} />
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
        <h3 className="text-sm font-semibold text-neutral-900">Quiz settings</h3>
        <Input id={`quiz-title-${quiz.id}`} label="Title" required value={title} onChange={(e) => setTitle(e.target.value)} />
        <div className="grid grid-cols-3 gap-4">
          <Input
            id={`quiz-pass-${quiz.id}`}
            label="Pass %"
            type="number"
            min={0}
            max={100}
            value={passPercentage}
            onChange={(e) => setPassPercentage(Number(e.target.value))}
          />
          <Input
            id={`quiz-time-${quiz.id}`}
            label="Time limit (min)"
            type="number"
            value={timeLimitMinutes}
            onChange={(e) => setTimeLimitMinutes(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="No limit"
          />
          <Input
            id={`quiz-attempts-${quiz.id}`}
            label="Max attempts"
            type="number"
            value={maxAttempts}
            onChange={(e) => setMaxAttempts(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="Unlimited"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-neutral-700">
          <input type="checkbox" checked={randomizeQuestions} onChange={(e) => setRandomizeQuestions(e.target.checked)} />
          Randomize question order
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {saveSuccess && <p className="text-sm text-emerald-600">Saved.</p>}

        <Button type="submit" size="sm" disabled={isSaving}>
          {isSaving ? 'Saving…' : 'Save settings'}
        </Button>
      </form>

      <div className="border-t border-neutral-200 pt-4">
        <h3 className="text-sm font-semibold text-neutral-900">Questions</h3>
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
              className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
            />
            <button type="button" onClick={() => void handleAddQuestion()} className="text-sm font-medium text-brand-navy hover:underline">
              Add
            </button>
            <button type="button" onClick={() => setIsAddingQuestion(false)} className="text-sm text-neutral-500 hover:underline">
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsAddingQuestion(true)}
            className="mt-4 text-sm font-medium text-brand-navy hover:underline"
          >
            + Add question
          </button>
        )}
      </div>
    </div>
  )
}
