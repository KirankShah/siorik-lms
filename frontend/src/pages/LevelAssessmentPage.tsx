import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChoiceQuestionAnswer } from '../components/ChoiceQuestionAnswer'
import { ChoiceQuestionResult } from '../components/ChoiceQuestionResult'
import { QuestionFeedback } from '../components/QuestionFeedback'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import {
  fetchLevelAssessmentAttempt,
  fetchMyAssessmentLevel,
  startLevelAssessmentAttempt,
  submitLevelAssessmentAttempt,
} from '../lib/levelAssessmentsApi'
import type { AssessmentLevelSummary, LevelAssessmentAttempt, LevelAssessmentStatus } from '../types/levelAssessments'

type Stage = 'loading' | 'not_assigned' | 'landing' | 'in_progress' | 'submitting' | 'results' | 'error'

const DEFAULT_SECONDS_PER_QUESTION = 60
// How long the "Time's up — 0 marks" message stays on screen before
// auto-advancing — long enough to actually read it, short enough not to
// stall the assessment.
const TIMEOUT_MESSAGE_DELAY_MS = 1800

function buildInitialAnswers(attempt: LevelAssessmentAttempt): Record<number, Set<number>> {
  const initial: Record<number, Set<number>> = {}
  for (const question of attempt.questions) {
    initial[question.id] = new Set()
  }
  return initial
}

export function LevelAssessmentPage() {
  const [stage, setStage] = useState<Stage>('loading')
  const [assessmentLevel, setAssessmentLevel] = useState<AssessmentLevelSummary | null>(null)
  const [lastStatus, setLastStatus] = useState<LevelAssessmentStatus | null>(null)
  const [attempt, setAttempt] = useState<LevelAssessmentAttempt | null>(null)
  const [answers, setAnswers] = useState<Record<number, Set<number>>>({})
  const [error, setError] = useState<string | null>(null)

  // Sequential flow state — a single question shown at a time, no skipping
  // ahead and no returning to a previous one once currentIndex advances past
  // it (there is simply no control anywhere in this UI that can move it
  // backwards or set it to an arbitrary value).
  const [currentIndex, setCurrentIndex] = useState(0)
  const [timeLeft, setTimeLeft] = useState(0)
  const [questionLocked, setQuestionLocked] = useState(false)

  const secondsPerQuestion = assessmentLevel?.seconds_per_question ?? DEFAULT_SECONDS_PER_QUESTION

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const myStatus = await fetchMyAssessmentLevel()
        if (cancelled) return

        if (!myStatus.assigned || !myStatus.assessment_level) {
          setStage('not_assigned')
          return
        }
        setAssessmentLevel(myStatus.assessment_level)
        setLastStatus(myStatus.status ?? null)

        if (myStatus.status === 'IN_PROGRESS' && myStatus.open_attempt_id) {
          const openAttempt = await fetchLevelAssessmentAttempt(myStatus.open_attempt_id)
          if (cancelled) return
          setAttempt(openAttempt)
          setAnswers(buildInitialAnswers(openAttempt))
          setCurrentIndex(0)
          setQuestionLocked(false)
          setStage('in_progress')
        } else {
          setStage('landing')
        }
      } catch {
        if (!cancelled) setStage('error')
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  const currentQuestion = attempt?.questions[currentIndex] ?? null
  const hasAnswer = currentQuestion ? (answers[currentQuestion.id]?.size ?? 0) > 0 : false

  // Kept in sync below and read inside the interval callback so it always
  // sees the *current* answered state rather than the one captured when the
  // interval was created — a plain closure over `hasAnswer` would go stale
  // the moment the learner answers, since the interval itself is only
  // (re)created once per question, not on every keystroke/selection.
  const hasAnswerRef = useRef(hasAnswer)
  useEffect(() => {
    hasAnswerRef.current = hasAnswer
  }, [hasAnswer])

  // The countdown, one interval per question — resets on entry and owns its
  // own decrement-and-lock decision entirely through functional setState
  // updates (`setTimeLeft(t => ...)`), rather than a second effect reading
  // `timeLeft` back out of render state. Reading it back was the original
  // bug here: on the very first render where `stage` becomes 'in_progress',
  // a separate "tick" effect and this "reset" effect both ran in the same
  // commit, and the tick effect saw `timeLeft`'s stale pre-reset value (0,
  // its initial state) before the reset's setTimeLeft(secondsPerQuestion)
  // had actually applied — locking the question instantly, every time,
  // rather than ever visibly counting down. A single effect avoids that
  // entirely: there's no other code path that can observe `timeLeft` before
  // this effect's own reset has taken effect.
  useEffect(() => {
    if (stage !== 'in_progress') return
    setQuestionLocked(false)
    setTimeLeft(secondsPerQuestion)

    const interval = setInterval(() => {
      if (hasAnswerRef.current) return // frozen once answered — see hasAnswerRef above
      setTimeLeft((t) => {
        if (t <= 1) {
          clearInterval(interval)
          setQuestionLocked(true)
          return 0
        }
        return t - 1
      })
    }, 1000)

    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex, stage, secondsPerQuestion])

  function goToNextOrFinish() {
    if (!attempt) return
    const isLast = currentIndex === attempt.questions.length - 1
    if (isLast) {
      void handleSubmit()
    } else {
      setCurrentIndex((i) => i + 1)
    }
  }

  // Auto-advance (or auto-submit, on the last question) after the "Time's
  // up" message has had a moment to be read.
  useEffect(() => {
    if (!questionLocked) return
    const timeout = setTimeout(goToNextOrFinish, TIMEOUT_MESSAGE_DELAY_MS)
    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionLocked])

  async function handleStart() {
    setStage('loading')
    setError(null)
    try {
      const newAttempt = await startLevelAssessmentAttempt()
      setAttempt(newAttempt)
      setAnswers(buildInitialAnswers(newAttempt))
      setCurrentIndex(0)
      setQuestionLocked(false)
      setStage('in_progress')
    } catch {
      setError('Could not start the assessment. Please try again.')
      setStage('landing')
    }
  }

  function toggleChoice(questionId: number, choiceId: number, isMultiple: boolean) {
    if (questionLocked) return
    setAnswers((prev) => {
      const selected = new Set(prev[questionId] ?? [])
      if (isMultiple) {
        if (selected.has(choiceId)) selected.delete(choiceId)
        else selected.add(choiceId)
      } else {
        selected.clear()
        selected.add(choiceId)
      }
      return { ...prev, [questionId]: selected }
    })
  }

  async function handleSubmit() {
    if (!attempt) return
    setStage('submitting')
    setError(null)
    try {
      const payload = attempt.questions.map((question) => ({
        question: question.id,
        selected_choices: Array.from(answers[question.id] ?? []),
      }))
      const result = await submitLevelAssessmentAttempt(attempt.id, payload)
      setAttempt(result)
      setLastStatus(result.passed ? 'PASSED' : 'FAILED')
      setStage('results')
    } catch {
      setError('Could not submit the assessment. Please try again.')
      setStage('in_progress')
    }
  }

  if (stage === 'loading') {
    return <p className="text-sm text-neutral-500">Loading…</p>
  }

  if (stage === 'error') {
    return <p className="text-sm text-red-600">Could not load your assessment. Please try again.</p>
  }

  if (stage === 'not_assigned') {
    return (
      <Card className="text-center">
        <p className="text-sm text-neutral-500">You don't have a role-based assessment assigned yet.</p>
      </Card>
    )
  }

  if (stage === 'landing' && assessmentLevel) {
    const isRetake = lastStatus === 'PASSED' || lastStatus === 'FAILED'
    return (
      <Card className="text-center">
        <h1 className="text-base font-semibold text-neutral-900">{assessmentLevel.name_display} Assessment</h1>
        <p className="mt-2 text-sm text-neutral-500">
          {assessmentLevel.questions_per_attempt} question{assessmentLevel.questions_per_attempt === 1 ? '' : 's'} · Pass
          mark: {assessmentLevel.pass_threshold}% · {assessmentLevel.seconds_per_question}s per question
        </p>
        <p className="mt-1 text-xs text-neutral-400">
          Questions are shown one at a time. Once you move on you can't go back, and an unanswered question locks at
          zero marks when its timer runs out.
        </p>
        {lastStatus === 'FAILED' && (
          <p className="mt-2 text-sm text-red-600">You did not pass your last attempt — you may retake it now.</p>
        )}
        {lastStatus === 'PASSED' && <p className="mt-2 text-sm text-emerald-700">You've already passed this assessment.</p>}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <Button className="mt-4" onClick={handleStart}>
          {isRetake ? 'Retake Assessment' : 'Start Assessment'}
        </Button>
      </Card>
    )
  }

  if ((stage === 'in_progress' || stage === 'submitting') && attempt && currentQuestion) {
    const isLast = currentIndex === attempt.questions.length - 1
    const timePercent = Math.max(0, Math.min(100, (timeLeft / secondsPerQuestion) * 100))
    const barColor = timePercent <= 20 ? 'bg-red-500' : timePercent <= 50 ? 'bg-brand-gold' : 'bg-brand-navy'

    return (
      <Card>
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-base font-semibold text-neutral-900">{attempt.assessment_level_name} Assessment</h1>
          <span className="shrink-0 text-xs font-medium text-neutral-400">
            Question {currentIndex + 1} of {attempt.questions.length}
          </span>
        </div>

        {/* Depleting countdown bar — frozen once answered, see the timer effect above. */}
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
          <div
            className={`h-full rounded-full transition-all duration-1000 ease-linear ${barColor}`}
            style={{ width: `${timePercent}%` }}
          />
        </div>
        <p className="mt-1 text-right text-xs text-neutral-400">{questionLocked ? '0' : timeLeft}s</p>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <div className="mt-4 rounded-lg border border-neutral-200 p-4">
          <div className="flex items-start justify-between gap-4">
            <div
              className="min-w-0 flex-1 text-sm font-medium text-neutral-900 [overflow-wrap:anywhere]"
              dangerouslySetInnerHTML={{ __html: currentQuestion.question_text }}
            />
            <span className="shrink-0 text-sm font-normal text-neutral-400">
              ({currentQuestion.marks} {currentQuestion.marks === 1 ? 'mark' : 'marks'})
            </span>
          </div>

          {questionLocked ? (
            <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
              Time's up — 0 marks for this question.
            </p>
          ) : (
            <div className="mt-3">
              <ChoiceQuestionAnswer
                questionId={currentQuestion.id}
                isMultiple={currentQuestion.question_type === 'MULTIPLE_ANSWER'}
                choices={currentQuestion.choices}
                selected={answers[currentQuestion.id] ?? new Set()}
                onToggle={(choiceId) =>
                  toggleChoice(currentQuestion.id, choiceId, currentQuestion.question_type === 'MULTIPLE_ANSWER')
                }
              />
            </div>
          )}
        </div>

        {!questionLocked && (
          <Button
            className="mt-6"
            disabled={!hasAnswer || stage === 'submitting'}
            onClick={goToNextOrFinish}
          >
            {stage === 'submitting' ? 'Submitting…' : isLast ? 'Finish' : 'Next'}
          </Button>
        )}
      </Card>
    )
  }

  if (stage === 'results' && attempt) {
    return (
      <Card>
        <div className={`rounded-lg p-4 ${attempt.passed ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'}`}>
          <p className="text-lg font-semibold">{attempt.passed ? 'You passed!' : 'You did not pass'}</p>
          <p className="text-sm">
            Score: {attempt.score_percent}% (pass mark: {attempt.pass_threshold}%)
          </p>
        </div>

        <div className="mt-6 space-y-4">
          {attempt.questions.map((question) => {
            const answer = attempt.answers.find((a) => a.question === question.id)
            return (
              <div key={question.id} className="rounded-lg border border-neutral-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div
                    className="min-w-0 flex-1 text-sm font-medium text-neutral-900 [overflow-wrap:anywhere]"
                    dangerouslySetInnerHTML={{ __html: question.question_text }}
                  />
                  <span className={`shrink-0 text-xs font-medium ${answer?.is_correct ? 'text-emerald-600' : 'text-red-600'}`}>
                    {answer?.is_correct ? 'Correct' : 'Incorrect'}
                  </span>
                </div>

                <ChoiceQuestionResult
                  choices={question.choices}
                  selectedIds={answer?.selected_choices ?? []}
                  correctIds={answer?.correct_choice_ids ?? []}
                />

                <QuestionFeedback
                  explanation={answer?.explanation}
                  isCorrect={answer?.is_correct}
                  feedbackCorrect={answer?.feedback_correct}
                  feedbackIncorrect={answer?.feedback_incorrect}
                />
              </div>
            )
          })}
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/dashboard" className="inline-flex">
            <Button variant="secondary">Back to Dashboard</Button>
          </Link>
          {!attempt.passed && <Button onClick={handleStart}>Retake Assessment</Button>}
        </div>
      </Card>
    )
  }

  return null
}
