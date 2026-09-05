import { useEffect, useState } from 'react'
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

  async function handleStart() {
    setStage('loading')
    setError(null)
    try {
      const newAttempt = await startLevelAssessmentAttempt()
      setAttempt(newAttempt)
      setAnswers(buildInitialAnswers(newAttempt))
      setStage('in_progress')
    } catch {
      setError('Could not start the assessment. Please try again.')
      setStage('landing')
    }
  }

  function toggleChoice(questionId: number, choiceId: number, isMultiple: boolean) {
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
          mark: {assessmentLevel.pass_threshold}%
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

  if ((stage === 'in_progress' || stage === 'submitting') && attempt) {
    return (
      <Card>
        <h1 className="text-base font-semibold text-neutral-900">{attempt.assessment_level_name} Assessment</h1>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <div className="mt-4 space-y-6">
          {attempt.questions.map((question, index) => (
            <div key={question.id} className="rounded-lg border border-neutral-200 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1 text-sm font-medium text-neutral-900">
                  <span className="text-neutral-400">{index + 1}.</span>{' '}
                  <div
                    className="inline-block w-full max-w-full align-top [overflow-wrap:anywhere]"
                    dangerouslySetInnerHTML={{ __html: question.question_text }}
                  />
                </div>
                <span className="shrink-0 text-sm font-normal text-neutral-400">
                  ({question.marks} {question.marks === 1 ? 'mark' : 'marks'})
                </span>
              </div>
              <div className="mt-3">
                <ChoiceQuestionAnswer
                  questionId={question.id}
                  isMultiple={question.question_type === 'MULTIPLE_ANSWER'}
                  choices={question.choices}
                  selected={answers[question.id] ?? new Set()}
                  onToggle={(choiceId) => toggleChoice(question.id, choiceId, question.question_type === 'MULTIPLE_ANSWER')}
                />
              </div>
            </div>
          ))}
        </div>

        <Button className="mt-6" disabled={stage === 'submitting'} onClick={handleSubmit}>
          {stage === 'submitting' ? 'Submitting…' : 'Submit'}
        </Button>
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
