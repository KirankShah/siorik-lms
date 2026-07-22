import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { downloadCertificate, issueCertificate } from '../lib/certificatesApi'
import { fetchQuizDetail, submitQuizAttempt } from '../lib/quizApi'
import type { Question, QuizAttemptResult, QuizDetail, QuizSummary } from '../types/quiz'

type Stage = 'intro' | 'loading' | 'in_progress' | 'submitting' | 'results'

function formatTime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

interface QuizPlayerProps {
  quizSummary: QuizSummary
  courseId: number
  onSubmitted?: () => void
}

export function QuizPlayer({ quizSummary, courseId, onSubmitted }: QuizPlayerProps) {
  const [stage, setStage] = useState<Stage>('intro')
  const [quiz, setQuiz] = useState<QuizDetail | null>(null)
  const [answers, setAnswers] = useState<Record<number, Set<number>>>({})
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null)
  const [result, setResult] = useState<QuizAttemptResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [certificateId, setCertificateId] = useState<number | null>(null)
  const [isPreparingCertificate, setIsPreparingCertificate] = useState(false)

  const handleSubmit = useCallback(
    async (currentQuiz: QuizDetail, currentAnswers: Record<number, Set<number>>) => {
      setStage('submitting')
      setError(null)
      try {
        const payload = currentQuiz.questions.map((question) => ({
          question: question.id,
          selected_choices: Array.from(currentAnswers[question.id] ?? []),
        }))
        const attempt = await submitQuizAttempt(currentQuiz.id, payload)
        setResult(attempt)
        setStage('results')
        onSubmitted?.()
      } catch (err) {
        if (err instanceof ApiError && err.status === 400) {
          const detail = (err.body as { detail?: string })?.detail
          setError(detail ?? 'Could not submit the quiz — you may have reached the maximum attempts.')
        } else {
          setError('Could not submit the quiz. Please try again.')
        }
        setStage('in_progress')
      }
    },
    [onSubmitted],
  )

  // Countdown timer — auto-submits when it reaches zero.
  useEffect(() => {
    if (stage !== 'in_progress' || remainingSeconds === null) return
    if (remainingSeconds <= 0) {
      if (quiz) handleSubmit(quiz, answers)
      return
    }
    const timeout = setTimeout(() => setRemainingSeconds((seconds) => (seconds ?? 1) - 1), 1000)
    return () => clearTimeout(timeout)
  }, [stage, remainingSeconds, quiz, answers, handleSubmit])

  async function startQuiz() {
    setStage('loading')
    setError(null)
    try {
      const detail = await fetchQuizDetail(quizSummary.id)
      setQuiz(detail)
      setAnswers({})
      setRemainingSeconds(detail.time_limit_minutes ? detail.time_limit_minutes * 60 : null)
      setStage('in_progress')
    } catch {
      setError('Could not load the quiz. Please try again.')
      setStage('intro')
    }
  }

  function toggleChoice(question: Question, choiceId: number) {
    setAnswers((prev) => {
      const next = { ...prev }
      const current = new Set(prev[question.id] ?? [])
      if (question.question_type === 'MULTIPLE_CHOICE') {
        if (current.has(choiceId)) current.delete(choiceId)
        else current.add(choiceId)
      } else {
        current.clear()
        current.add(choiceId)
      }
      next[question.id] = current
      return next
    })
  }

  async function handleDownloadCertificate() {
    setIsPreparingCertificate(true)
    setError(null)
    try {
      let id = certificateId
      if (!id) {
        const certificate = await issueCertificate(courseId)
        id = certificate.id
        setCertificateId(id)
        await downloadCertificate(id, `${certificate.certificate_number}.pdf`)
      } else {
        await downloadCertificate(id, 'certificate.pdf')
      }
    } catch {
      setError('Could not generate the certificate. Please try again.')
    } finally {
      setIsPreparingCertificate(false)
    }
  }

  if (stage === 'intro') {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">{quizSummary.title}</h2>
        <p className="mt-2 text-sm text-slate-500">
          Pass mark: {quizSummary.pass_percentage}%
          {quizSummary.time_limit_minutes && ` · Time limit: ${quizSummary.time_limit_minutes} min`}
          {quizSummary.max_attempts && ` · Max attempts: ${quizSummary.max_attempts}`}
        </p>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <button
          type="button"
          onClick={startQuiz}
          className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        >
          Start Quiz
        </button>
      </div>
    )
  }

  if (stage === 'loading') {
    return <p className="text-sm text-slate-500">Loading quiz…</p>
  }

  if ((stage === 'in_progress' || stage === 'submitting') && quiz) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">{quiz.title}</h2>
          {remainingSeconds !== null && (
            <span
              className={`rounded-md px-3 py-1 text-sm font-mono font-medium ${
                remainingSeconds <= 60 ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {formatTime(remainingSeconds)}
            </span>
          )}
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <div className="space-y-6">
          {quiz.questions.map((question, index) => (
            <div key={question.id} className="rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-medium text-slate-900">
                {index + 1}. {question.question_text}{' '}
                <span className="font-normal text-slate-400">
                  ({question.points} {question.points === 1 ? 'point' : 'points'})
                </span>
              </p>
              <div className="mt-3 space-y-2">
                {question.choices.map((choice) => {
                  const selected = answers[question.id]?.has(choice.id) ?? false
                  return (
                    <label
                      key={choice.id}
                      className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition ${
                        selected ? 'border-slate-900 bg-slate-50' : 'border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <input
                        type={question.question_type === 'MULTIPLE_CHOICE' ? 'checkbox' : 'radio'}
                        name={`question-${question.id}`}
                        checked={selected}
                        onChange={() => toggleChoice(question, choice.id)}
                        className="h-4 w-4"
                      />
                      {choice.choice_text}
                    </label>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          disabled={stage === 'submitting'}
          onClick={() => handleSubmit(quiz, answers)}
          className="mt-6 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {stage === 'submitting' ? 'Submitting…' : 'Submit'}
        </button>
      </div>
    )
  }

  if (stage === 'results' && result && quiz) {
    const canRetake = !result.passed && (quiz.max_attempts === null || result.attempt_number < quiz.max_attempts)

    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div
          className={`rounded-lg p-4 ${
            result.passed ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'
          }`}
        >
          <p className="text-lg font-semibold">{result.passed ? 'You passed!' : 'You did not pass'}</p>
          <p className="text-sm">
            Score: {result.score_percent}% (pass mark: {quiz.pass_percentage}%)
          </p>
        </div>

        <div className="mt-6 space-y-4">
          {quiz.questions.map((question) => {
            const answer = result.answers.find((a) => a.question === question.id)
            return (
              <div key={question.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <p className="text-sm font-medium text-slate-900">{question.question_text}</p>
                  <span
                    className={`shrink-0 text-xs font-medium ${
                      answer?.is_correct ? 'text-emerald-600' : 'text-red-600'
                    }`}
                  >
                    {answer?.is_correct ? 'Correct' : 'Incorrect'}
                  </span>
                </div>
                <ul className="mt-2 space-y-1">
                  {question.choices.map((choice) => {
                    const wasSelected = answer?.selected_choices.includes(choice.id) ?? false
                    // choice.is_correct is only present when the backend allows this
                    // role to see it — undefined for learners, so we just show what
                    // they picked without revealing the actual correct answer.
                    const knownCorrect = choice.is_correct === true
                    return (
                      <li
                        key={choice.id}
                        className={`text-sm ${
                          knownCorrect
                            ? 'font-medium text-emerald-700'
                            : wasSelected
                              ? 'text-slate-900'
                              : 'text-slate-500'
                        }`}
                      >
                        {wasSelected ? '●' : '○'} {choice.choice_text}
                        {knownCorrect && ' (correct answer)'}
                      </li>
                    )
                  })}
                </ul>
              </div>
            )
          })}
        </div>

        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        <div className="mt-6 flex gap-3">
          {canRetake && (
            <button
              type="button"
              onClick={() => setStage('intro')}
              className="rounded-md border border-slate-900 px-4 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-900 hover:text-white"
            >
              Retake Quiz
            </button>
          )}
          {result.passed && (
            <button
              type="button"
              disabled={isPreparingCertificate}
              onClick={handleDownloadCertificate}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isPreparingCertificate ? 'Preparing…' : 'Download Certificate'}
            </button>
          )}
        </div>
      </div>
    )
  }

  return null
}
