import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Clock3 } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import {
  advancePeriodicExamAttempt,
  fetchPeriodicExamAttempt,
  savePeriodicExamAnswer,
  submitPeriodicExamAttempt,
} from '../lib/periodicExamsApi'
import type { PeriodicExamAttempt } from '../types/periodicExams'

type RetryAction = 'load' | 'save' | 'advance' | 'submit' | 'expired'

export function PeriodicExamAttemptPage() {
  const { attemptId } = useParams()
  const navigate = useNavigate()
  const id = Number(attemptId)
  const [attempt, setAttempt] = useState<PeriodicExamAttempt | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [remainingSeconds, setRemainingSeconds] = useState(0)
  const [busy, setBusy] = useState(false)
  const [lockedMessage, setLockedMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retryAction, setRetryAction] = useState<RetryAction | null>(null)
  const activeRequest = useRef(false)

  const acceptAttempt = useCallback((value: PeriodicExamAttempt) => {
    setAttempt(value)
    setRemainingSeconds(value.remaining_seconds)
    setSelected(value.current_question?.selected_option_keys ?? [])
    if (value.submitted) navigate(`/periodic-exam/attempt/${value.id}/result`, { replace: true })
  }, [navigate])

  const perform = useCallback(async (action: RetryAction, request: () => Promise<PeriodicExamAttempt>) => {
    if (activeRequest.current) return
    activeRequest.current = true
    setBusy(true)
    setError(null)
    setRetryAction(null)
    try {
      acceptAttempt(await request())
    } catch {
      setError('The server could not confirm that action. Check your connection and retry safely.')
      setRetryAction(action)
    } finally {
      activeRequest.current = false
      setBusy(false)
    }
  }, [acceptAttempt])

  const load = useCallback(async () => {
    if (!Number.isInteger(id)) {
      setError('This attempt could not be found.')
      return
    }
    await perform('load', () => fetchPeriodicExamAttempt(id))
  }, [id, perform])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!attempt || attempt.submitted || remainingSeconds <= 0) return
    const timer = window.setTimeout(() => setRemainingSeconds((current) => Math.max(0, current - 1)), 1000)
    return () => window.clearTimeout(timer)
  }, [attempt, remainingSeconds])

  useEffect(() => {
    if (!attempt || attempt.submitted || remainingSeconds !== 0 || busy) return
    setLockedMessage('Time expired. Confirming the next question with the server…')
    void perform('expired', () => fetchPeriodicExamAttempt(attempt.id)).finally(() => setLockedMessage(null))
  }, [attempt, busy, perform, remainingSeconds])

  useEffect(() => {
    if (!attempt || attempt.submitted) return
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    const protectLinks = (event: MouseEvent) => {
      const link = (event.target as HTMLElement).closest('a')
      if (link && !window.confirm('Your exam is in progress. Leave this page?')) {
        event.preventDefault()
        event.stopPropagation()
      }
    }
    window.addEventListener('beforeunload', beforeUnload)
    document.addEventListener('click', protectLinks, true)
    return () => {
      window.removeEventListener('beforeunload', beforeUnload)
      document.removeEventListener('click', protectLinks, true)
    }
  }, [attempt])

  async function choose(key: string) {
    if (!attempt?.current_question || busy || remainingSeconds <= 0) return
    const next = attempt.current_question.question_type === 'SINGLE_CHOICE'
      ? [key]
      : selected.includes(key) ? selected.filter((value) => value !== key) : [...selected, key]
    setSelected(next)
    await perform('save', () => savePeriodicExamAnswer(attempt.id, attempt.current_question_index, next))
  }

  async function moveForward() {
    if (!attempt || busy || remainingSeconds <= 0) return
    const isLast = attempt.current_question_index + 1 === attempt.total_questions
    await perform(
      isLast ? 'submit' : 'advance',
      () => isLast
        ? submitPeriodicExamAttempt(attempt.id)
        : advancePeriodicExamAttempt(attempt.id, attempt.current_question_index),
    )
  }

  function retry() {
    if (!retryAction || !attempt) {
      void load()
      return
    }
    if (retryAction === 'load' || retryAction === 'expired') {
      void perform(retryAction, () => fetchPeriodicExamAttempt(attempt.id))
    } else if (retryAction === 'save') {
      void perform('save', () => savePeriodicExamAnswer(attempt.id, attempt.current_question_index, selected))
    } else if (retryAction === 'submit') {
      void perform('submit', () => submitPeriodicExamAttempt(attempt.id))
    } else {
      void perform('advance', () => advancePeriodicExamAttempt(attempt.id, attempt.current_question_index))
    }
  }

  if (!attempt) {
    return (
      <div className="text-sm">
        <p className={error ? 'text-red-600' : 'text-neutral-500'}>{error ?? 'Resuming your exam…'}</p>
        {error && <Button className="mt-3" onClick={retry}>Retry</Button>}
      </div>
    )
  }

  const question = attempt.current_question
  if (!question) return <p className="text-sm text-red-600">The current question could not be loaded.</p>
  const isLast = attempt.current_question_index + 1 === attempt.total_questions

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-neutral-500">Question {attempt.current_question_index + 1} of {attempt.total_questions}</p>
          <div className="mt-2 h-1.5 w-48 overflow-hidden rounded-full bg-neutral-200">
            <div className="h-full bg-brand-gold" style={{ width: `${((attempt.current_question_index + 1) / attempt.total_questions) * 100}%` }} />
          </div>
        </div>
        <div className={`flex items-center gap-2 rounded-full px-4 py-2 font-semibold ${remainingSeconds <= 10 ? 'bg-red-50 text-red-700' : 'bg-brand-navy/5 text-brand-navy'}`}>
          <Clock3 className="h-5 w-5" aria-hidden="true" />
          <span aria-label={`${remainingSeconds} seconds remaining`}>{remainingSeconds}s</span>
        </div>
      </div>

      <Card>
        <h1 className="text-xl font-semibold text-neutral-900">{question.question_text}</h1>
        <p className="mt-2 text-sm text-neutral-500">
          {question.question_type === 'MULTIPLE_ANSWER' ? 'Select all answers that apply.' : 'Select one answer.'}
        </p>
        <div className="mt-6 space-y-3">
          {question.choices.map((choice) => {
            const checked = selected.includes(choice.key)
            return (
              <label key={choice.key} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition ${checked ? 'border-brand-navy bg-brand-navy/5' : 'border-neutral-200 hover:border-neutral-300'}`}>
                <input
                  type={question.question_type === 'MULTIPLE_ANSWER' ? 'checkbox' : 'radio'}
                  name="periodic-exam-answer"
                  checked={checked}
                  disabled={busy || remainingSeconds <= 0}
                  onChange={() => void choose(choice.key)}
                  className="mt-0.5"
                />
                <span className="text-sm text-neutral-800">{choice.text}</span>
              </label>
            )
          })}
        </div>
      </Card>

      {lockedMessage && <p role="status" className="text-sm text-amber-700">{lockedMessage}</p>}
      {error && (
        <div role="alert" className="flex items-start justify-between gap-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <span className="flex gap-2"><AlertTriangle className="h-5 w-5 shrink-0" />{error}</span>
          <Button size="sm" variant="outline" onClick={retry} disabled={busy}>Retry</Button>
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={() => void moveForward()} disabled={busy || remainingSeconds <= 0}>
          {busy ? 'Saving…' : isLast ? 'Submit exam' : 'Save and continue'}
        </Button>
      </div>
      <p className="text-center text-xs text-neutral-500">You cannot return to a previous question.</p>
    </div>
  )
}
