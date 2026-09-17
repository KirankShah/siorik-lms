import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChoiceQuestionAnswer } from '../components/ChoiceQuestionAnswer'
import { ChoiceQuestionResult } from '../components/ChoiceQuestionResult'
import { QuestionFeedback } from '../components/QuestionFeedback'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ApiError } from '../lib/apiClient'
import {
  advanceLevelAssessmentAttempt,
  fetchLevelAssessmentAttempt,
  fetchMyAssessmentLevel,
  saveLevelAssessmentAnswerProgress,
  startLevelAssessmentAttempt,
  submitLevelAssessmentAttempt,
} from '../lib/levelAssessmentsApi'
import type { AssessmentLevelSummary, LevelAssessmentAttempt, LevelAssessmentStatus } from '../types/levelAssessments'

type Stage = 'loading' | 'not_assigned' | 'landing' | 'in_progress' | 'submitting' | 'results' | 'error'

const DEFAULT_SECONDS_PER_QUESTION = 60
const DEFAULT_TOTAL_EXAM_MINUTES = 60
// How long the "Time's up — 0 marks" message stays on screen before
// auto-advancing — long enough to actually read it, short enough not to
// stall the assessment.
const TIMEOUT_MESSAGE_DELAY_MS = 1800

function buildAnswersFromAttempt(attempt: LevelAssessmentAttempt): Record<number, Set<number>> {
  const initial: Record<number, Set<number>> = {}
  for (const question of attempt.questions) {
    // Resume support: prefills whatever was already saved via save-answer
    // before a crash/closure — see answers_so_far on the backend model.
    initial[question.id] = new Set(attempt.answers_so_far[String(question.id)] ?? [])
  }
  return initial
}

function formatMinutesSeconds(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function extractErrorDetail(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.body && typeof err.body === 'object') {
    const detail = (err.body as { detail?: string }).detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}

export function LevelAssessmentPage() {
  const [stage, setStage] = useState<Stage>('loading')
  const [assessmentLevel, setAssessmentLevel] = useState<AssessmentLevelSummary | null>(null)
  const [lastStatus, setLastStatus] = useState<LevelAssessmentStatus | null>(null)
  const [attempt, setAttempt] = useState<LevelAssessmentAttempt | null>(null)
  const [answers, setAnswers] = useState<Record<number, Set<number>>>({})
  const [error, setError] = useState<string | null>(null)
  // Set when the learner already has an open (unsubmitted) attempt — the
  // landing/declaration screen still shows first either way (see the load()
  // effect below and its own comment); this just tells that screen's button
  // whether to resume this attempt instead of starting a brand new one.
  const [pendingOpenAttemptId, setPendingOpenAttemptId] = useState<number | null>(null)
  // None = unlimited (org's max_level_assessment_attempts unset); otherwise
  // how many more attempts remain — 0 disables starting/retaking, with an
  // explanation, before the learner even tries (the backend enforces the
  // same cap regardless, as a defense-in-depth backstop).
  const [attemptsRemaining, setAttemptsRemaining] = useState<number | null>(null)

  // PER_QUESTION mode only — resets every question, seeded from the
  // server-computed attempt.remaining_seconds (see the timer effect below),
  // not always the full per-question allocation, so a fresh start, a resumed
  // attempt, and an ordinary question-to-question advance all behave
  // correctly through the exact same code path.
  const [timeLeft, setTimeLeft] = useState(0)
  const [questionLocked, setQuestionLocked] = useState(false)
  // FIXED_TOTAL mode only — one countdown for the whole attempt, persisting
  // across every question (see the overall-timer effect below). Also seeded
  // from attempt.remaining_seconds, once per attempt (start or resume), and
  // left running uninterrupted across every subsequent question change.
  const [overallTimeLeft, setOverallTimeLeft] = useState(0)
  // Set right before an auto-submit triggered by the FIXED_TOTAL overall
  // timer reaching zero, so the results screen can explain why.
  const [autoSubmitReason, setAutoSubmitReason] = useState<'time_expired' | null>(null)

  const timingMode = assessmentLevel?.timing_mode ?? 'PER_QUESTION'
  const secondsPerQuestion = assessmentLevel?.seconds_per_question ?? DEFAULT_SECONDS_PER_QUESTION
  // Rounded defensively — total_exam_minutes is always a whole number from
  // the backend, but this keeps the countdown exact even so.
  const totalExamSeconds = Math.round((assessmentLevel?.total_exam_minutes ?? DEFAULT_TOTAL_EXAM_MINUTES) * 60)
  // The single source of truth for "which question" — the server's own
  // current_question_index (updated via `advance`, and by the resume
  // catch-up on the backend) rather than a separate, potentially-divergent
  // piece of local state.
  const currentIndex = attempt?.current_question_index ?? 0

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
        setAttemptsRemaining(myStatus.attempts_remaining ?? null)
        // The landing/declaration screen always shows first — including when
        // resuming an already-open attempt (e.g. after a page reload), since
        // "before any question is shown" applies there too. Only the button's
        // behavior differs once clicked (resume vs. a fresh start) — see
        // handleContinue below.
        setPendingOpenAttemptId(myStatus.status === 'IN_PROGRESS' ? (myStatus.open_attempt_id ?? null) : null)
        setStage('landing')
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

  // Always points at the latest handleSubmit closure, read from inside the
  // FIXED_TOTAL interval below (defined further down, but function
  // declarations are hoisted) — runs after every render, deliberately with
  // no dependency array, so a submit triggered by the overall timer hitting
  // zero always sees the attempt/answers as of that exact moment.
  const handleSubmitRef = useRef<() => void>(() => {})
  useEffect(() => {
    handleSubmitRef.current = () => void handleSubmit()
  })

  // PER_QUESTION mode: the countdown, one interval per question — resets on
  // entry (seeded from attempt.remaining_seconds, computed server-side) and
  // owns its own decrement-and-lock decision entirely through functional
  // setState updates (`setTimeLeft(t => ...)`), rather than a second effect
  // reading `timeLeft` back out of render state. Reading it back was the
  // original bug here: on the very first render where `stage` becomes
  // 'in_progress', a separate "tick" effect and this "reset" effect both ran
  // in the same commit, and the tick effect saw `timeLeft`'s stale pre-reset
  // value (0, its initial state) before the reset had actually applied —
  // locking the question instantly, every time, rather than ever visibly
  // counting down. A single effect avoids that entirely: there's no other
  // code path that can observe `timeLeft` before this effect's own reset has
  // taken effect. Keyed on attempt?.id too, not just current_question_index,
  // so a brand new attempt that happens to start at the same index a prior
  // one ended on (e.g. both single-question) still reseeds correctly.
  useEffect(() => {
    if (timingMode !== 'PER_QUESTION' || stage !== 'in_progress' || !attempt) return
    setQuestionLocked(false)
    setTimeLeft(attempt.remaining_seconds)

    const interval = setInterval(() => {
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
  }, [attempt?.id, attempt?.current_question_index, stage, timingMode])

  // FIXED_TOTAL mode: one countdown for the entire attempt — deliberately
  // keyed on attempt?.id only (not current_question_index, and not stage) so
  // it starts once when a new attempt begins (seeded from
  // attempt.remaining_seconds — the full allocation for a fresh start, or
  // correctly less for a resume) and keeps running unattended across every
  // question, never resetting or freezing just because the current question
  // changed or was answered (unlike the PER_QUESTION timer above, this one
  // only cares about total elapsed exam time). Hitting zero triggers the
  // auto-submit directly from inside this same interval's own decrement
  // logic — NOT from a separate effect watching `overallTimeLeft === 0`,
  // which would be indistinguishable from that state variable's own
  // pre-reset initial value (also 0) and would fire the submit immediately
  // on every mount, before the reset above has even applied. Same hazard,
  // same fix, as the PER_QUESTION timer's own comment above describes.
  useEffect(() => {
    if (timingMode !== 'FIXED_TOTAL' || !attempt) return
    setOverallTimeLeft(attempt.remaining_seconds)

    const interval = setInterval(() => {
      setOverallTimeLeft((t) => {
        if (t <= 1) {
          clearInterval(interval)
          setAutoSubmitReason('time_expired')
          handleSubmitRef.current()
          return 0
        }
        return t - 1
      })
    }, 1000)

    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt?.id, timingMode])

  // Auto-advance (or auto-submit, on the last question) after the "Time's
  // up" message has had a moment to be read — PER_QUESTION mode only.
  useEffect(() => {
    if (!questionLocked) return
    const timeout = setTimeout(() => void goToNextOrFinish(), TIMEOUT_MESSAGE_DELAY_MS)
    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionLocked])

  async function goToNextOrFinish() {
    if (!attempt) return
    const isLast = currentIndex === attempt.questions.length - 1
    if (isLast) {
      await handleSubmit()
      return
    }
    // Tells the server to move on (and, under PER_QUESTION timing, reset the
    // new question's own countdown) BEFORE advancing locally — the server
    // always needs to know exactly where the learner is for resume to work
    // correctly after a crash right around this moment.
    try {
      const updated = await advanceLevelAssessmentAttempt(attempt.id, currentIndex + 1)
      if (updated.submitted_at) {
        // The server's own away-time catch-up (resume_level_assessment_attempt,
        // now run on every advance/submit, not just a resume-after-reload GET)
        // found the exam's time had already fully elapsed and auto-submitted
        // on the learner's behalf before this advance could go through — same
        // situation handleResume already handles for the reload path.
        setAttempt(updated)
        setAutoSubmitReason('time_expired')
        setLastStatus(updated.passed ? 'PASSED' : 'FAILED')
        setPendingOpenAttemptId(null)
        setAttemptsRemaining((prev) => (prev === null ? null : Math.max(0, prev - 1)))
        setStage('results')
        return
      }
      setAttempt(updated)
    } catch {
      setError('Could not move to the next question. Please try again.')
    }
  }

  async function handleStart() {
    setStage('loading')
    setError(null)
    setAutoSubmitReason(null)
    try {
      const newAttempt = await startLevelAssessmentAttempt()
      setAttempt(newAttempt)
      setAnswers(buildAnswersFromAttempt(newAttempt))
      setQuestionLocked(false)
      setStage('in_progress')
    } catch (err) {
      setError(extractErrorDetail(err, 'Could not start the assessment. Please try again.'))
      setStage('landing')
    }
  }

  async function handleResume(openAttemptId: number) {
    setStage('loading')
    setError(null)
    setAutoSubmitReason(null)
    try {
      // Applies the away-time catch-up server-side (see backend
      // resume_level_assessment_attempt) — the response already reflects
      // any auto-advance/auto-submit that should have happened live.
      const openAttempt = await fetchLevelAssessmentAttempt(openAttemptId)
      setAttempt(openAttempt)
      setAnswers(buildAnswersFromAttempt(openAttempt))
      setQuestionLocked(false)
      if (openAttempt.submitted_at) {
        // The backend's own away-time catch-up (resume_level_assessment_attempt)
        // decided the whole exam's time had already run out before we even
        // got here, and auto-submitted on the learner's behalf.
        setAutoSubmitReason('time_expired')
        setLastStatus(openAttempt.passed ? 'PASSED' : 'FAILED')
        setPendingOpenAttemptId(null)
        setAttemptsRemaining((prev) => (prev === null ? null : Math.max(0, prev - 1)))
        setStage('results')
      } else {
        setStage('in_progress')
      }
    } catch {
      setError('Could not resume your assessment. Please try again.')
      setStage('landing')
    }
  }

  // The landing screen's single confirmation button — resumes the open
  // attempt if there is one, otherwise starts a brand new one. Either way,
  // this is the only path into 'in_progress', so the timer (of either mode)
  // never starts before this click.
  function handleContinue() {
    if (pendingOpenAttemptId !== null) {
      void handleResume(pendingOpenAttemptId)
    } else {
      void handleStart()
    }
  }

  function toggleChoice(questionId: number, choiceId: number, isMultiple: boolean) {
    if (questionLocked || !attempt) return
    setAnswers((prev) => {
      const selected = new Set(prev[questionId] ?? [])
      if (isMultiple) {
        if (selected.has(choiceId)) selected.delete(choiceId)
        else selected.add(choiceId)
      } else {
        selected.clear()
        selected.add(choiceId)
      }
      // Fire-and-forget: persisted for resume purposes only — the frontend's
      // own `answers` state here is already the source of truth for display
      // and for what actually gets submitted, so a slow/failed save doesn't
      // block the learner from continuing.
      void saveLevelAssessmentAnswerProgress(attempt.id, {
        question: questionId,
        selected_choices: Array.from(selected),
      }).catch(() => {})
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
      setPendingOpenAttemptId(null)
      setAttemptsRemaining((prev) => (prev === null ? null : Math.max(0, prev - 1)))
      setStage('results')
    } catch {
      setError('Could not submit the assessment. Please try again.')
      setStage('in_progress')
    }
  }

  if (stage === 'loading') {
    return <p className="mx-auto max-w-2xl text-sm text-neutral-500">Loading…</p>
  }

  if (stage === 'error') {
    return <p className="mx-auto max-w-2xl text-sm text-red-600">Could not load your assessment. Please try again.</p>
  }

  if (stage === 'not_assigned') {
    return (
      <div className="mx-auto max-w-2xl">
        <Card className="text-center">
          <p className="text-sm text-neutral-500">You don't have a role-based assessment assigned yet.</p>
        </Card>
      </div>
    )
  }

  if (stage === 'landing' && assessmentLevel) {
    const isResuming = pendingOpenAttemptId !== null
    const isRetake = !isResuming && (lastStatus === 'PASSED' || lastStatus === 'FAILED')
    const isFixedTotal = assessmentLevel.timing_mode === 'FIXED_TOTAL'
    const timeAllocationText = isFixedTotal
      ? `You will have ${assessmentLevel.total_exam_minutes} minutes for the entire exam; if time runs out before ` +
        'you finish, the exam will submit automatically with your answers so far, and any unanswered questions ' +
        'will be marked as zero.'
      : `You will have ${assessmentLevel.seconds_per_question} seconds to answer each question; once time runs ` +
        'out on a question, it will lock and be marked as unanswered.'
    const confirmLabel = isResuming ? "I'm Ready, Continue Exam" : "I'm Ready, Start Exam"
    const attemptsExhausted = !isResuming && attemptsRemaining === 0

    return (
      <div className="mx-auto max-w-2xl">
        <Card className="p-8 text-center sm:p-10">
          <h1 className="text-2xl font-bold text-neutral-900">{assessmentLevel.name_display} Assessment</h1>
          <p className="mt-2 text-base text-neutral-500">
            {assessmentLevel.questions_per_attempt} question{assessmentLevel.questions_per_attempt === 1 ? '' : 's'}{' '}
            · Pass mark: {assessmentLevel.pass_threshold}%
          </p>
          <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-neutral-700">{timeAllocationText}</p>

          <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-6 py-6 sm:px-8">
            <p className="text-center text-base font-semibold text-amber-900">Before You Begin</p>
            <ul className="mx-auto mt-3 w-fit list-disc space-y-2 pl-5 text-left text-sm text-amber-800">
              <li>Complete this assessment independently, without help from colleagues.</li>
              <li>No reference materials or notes.</li>
              <li>No search engines or AI tools during the exam.</li>
              <li>Ensure a stable internet connection before starting.</li>
            </ul>
            <p className="mx-auto mt-4 max-w-md text-center text-sm font-medium text-amber-900">
              Your results may be relied upon as evidence of your training and competency.
            </p>
          </div>

          <div className="mt-5 space-y-1.5">
            {!isResuming && lastStatus === 'FAILED' && (
              <p className="text-sm text-red-600">You did not pass your last attempt — you may retake it now.</p>
            )}
            {!isResuming && lastStatus === 'PASSED' && (
              <p className="text-sm text-emerald-700">You've already passed this assessment.</p>
            )}
            {!isResuming && attemptsRemaining !== null && attemptsRemaining > 0 && (
              <p className="text-xs text-neutral-400">
                {attemptsRemaining} attempt{attemptsRemaining === 1 ? '' : 's'} remaining.
              </p>
            )}
            {attemptsExhausted && (
              <p className="text-sm font-medium text-red-600">
                You have reached the maximum number of attempts for this assessment. Please contact your training
                administrator.
              </p>
            )}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>

          <Button size="lg" className="mt-6 px-10" onClick={handleContinue} disabled={attemptsExhausted}>
            {confirmLabel}
          </Button>
          {isRetake && !attemptsExhausted && (
            <p className="mt-3 text-xs text-neutral-400">Starting again begins a fresh, timed attempt.</p>
          )}
        </Card>
      </div>
    )
  }

  if ((stage === 'in_progress' || stage === 'submitting') && attempt && currentQuestion) {
    const isLast = currentIndex === attempt.questions.length - 1
    const isFixedTotal = timingMode === 'FIXED_TOTAL'
    const timePercent = isFixedTotal
      ? Math.max(0, Math.min(100, (overallTimeLeft / totalExamSeconds) * 100))
      : Math.max(0, Math.min(100, (timeLeft / secondsPerQuestion) * 100))
    const barColor = timePercent <= 20 ? 'bg-red-500' : timePercent <= 50 ? 'bg-brand-gold' : 'bg-brand-navy'
    const timeReadout = isFixedTotal ? `${formatMinutesSeconds(overallTimeLeft)} remaining` : `${questionLocked ? 0 : timeLeft}s`

    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <div className="flex items-center justify-between gap-4">
            <h1 className="text-base font-semibold text-neutral-900">{attempt.assessment_level_name} Assessment</h1>
            <span className="shrink-0 text-xs font-medium text-neutral-400">
              Question {currentIndex + 1} of {attempt.questions.length}
            </span>
          </div>

          {/* Depleting countdown bar — for PER_QUESTION, reset on each new
              question but never paused by selecting an answer; for FIXED_TOTAL,
              one continuous bar for the whole attempt. */}
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-linear ${barColor}`}
              style={{ width: `${timePercent}%` }}
            />
          </div>
          <p className="mt-1 text-right text-xs text-neutral-400">{timeReadout}</p>

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
              onClick={() => void goToNextOrFinish()}
            >
              {stage === 'submitting' ? 'Submitting…' : isLast ? 'Finish' : 'Next'}
            </Button>
          )}
        </Card>
      </div>
    )
  }

  if (stage === 'results' && attempt) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          {autoSubmitReason === 'time_expired' && (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Your exam time ran out, so it was submitted automatically. Any question you hadn't answered yet was
              marked at zero.
            </div>
          )}

          <div className={`rounded-lg p-4 ${attempt.passed ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'}`}>
            <p className="text-lg font-semibold">{attempt.passed ? 'You passed!' : 'You did not pass'}</p>
            <p className="text-sm">
              Score: {attempt.score_percent}% (pass mark: {attempt.pass_threshold}%)
            </p>
          </div>

          <div className="mt-6 space-y-4">
            {attempt.questions.map((question) => {
              if (question.removed) {
                return (
                  <div key={question.id} className="rounded-lg border border-neutral-200 bg-neutral-50 p-4">
                    <p className="text-sm text-neutral-500 italic">
                      This question has since been removed from the question bank.
                    </p>
                  </div>
                )
              }

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

          {attemptsRemaining === 0 && !attempt.passed && (
            <p className="mt-4 text-sm text-red-600">
              You have reached the maximum number of attempts for this assessment. Please contact your training
              administrator.
            </p>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/dashboard" className="inline-flex">
              <Button variant="secondary">Back to Dashboard</Button>
            </Link>
            {/* Routes back to the landing/declaration screen rather than
                starting a fresh attempt directly — every exam start (including
                a retake) must go through the explicit "I'm Ready" confirmation,
                which is also where the max-attempts cap is actually enforced. */}
            {!attempt.passed && attemptsRemaining !== 0 && (
              <Button
                onClick={() => {
                  setPendingOpenAttemptId(null)
                  setStage('landing')
                }}
              >
                Retake Assessment
              </Button>
            )}
          </div>
        </Card>
      </div>
    )
  }

  return null
}
