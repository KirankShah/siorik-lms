import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { downloadCertificate, issueCertificate } from '../lib/certificatesApi'
import { fetchQuizDetail, submitQuizAttempt } from '../lib/quizApi'
import { CategorizeAnswer } from './CategorizeAnswer'
import { HotspotAnswer } from './HotspotAnswer'
import { MatchingAnswer } from './MatchingAnswer'
import { OrderingAnswer } from './OrderingAnswer'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import type { Question, QuizAttemptResult, QuizDetail, QuizSummary } from '../types/quiz'

type Stage = 'intro' | 'loading' | 'in_progress' | 'submitting' | 'results'

// Choice-based types (single/multi-select, true/false, fill-blank) just need
// a set of chosen ids. ORDERING's answer is the sequence itself. MATCHING's
// is a target-id -> item-id assignment map (both ids are Choice ids — see
// MatchingAnswer for why that's enough to grade a placement). CATEGORIZE's
// is an item-id -> bucket-id map. HOTSPOT's is a set of HotspotRegion ids —
// kept distinct from CHOICE's set since they're a different id space.
type AnswerState =
  | { kind: 'CHOICE'; selected: Set<number> }
  | { kind: 'ORDERING'; order: number[] }
  | { kind: 'MATCHING'; assignments: Record<number, number> }
  | { kind: 'CATEGORIZE'; placements: Record<number, number> }
  | { kind: 'HOTSPOT'; selected: Set<number> }

function buildInitialAnswers(detail: QuizDetail): Record<number, AnswerState> {
  const initial: Record<number, AnswerState> = {}
  for (const question of detail.questions) {
    if (question.question_type === 'ORDERING') {
      initial[question.id] = { kind: 'ORDERING', order: question.choices.map((c) => c.id) }
    } else if (question.question_type === 'MATCHING') {
      initial[question.id] = { kind: 'MATCHING', assignments: {} }
    } else if (question.question_type === 'CATEGORIZE') {
      initial[question.id] = { kind: 'CATEGORIZE', placements: {} }
    } else if (question.question_type === 'HOTSPOT') {
      initial[question.id] = { kind: 'HOTSPOT', selected: new Set() }
    } else {
      initial[question.id] = { kind: 'CHOICE', selected: new Set() }
    }
  }
  return initial
}

interface AnswerPayload {
  selected_choices: number[]
  category_placements: { item: number; bucket: number }[]
  selected_regions: number[]
}

function buildAnswerPayload(answer: AnswerState | undefined): AnswerPayload {
  const empty = { selected_choices: [], category_placements: [], selected_regions: [] }
  if (!answer) return empty
  if (answer.kind === 'CHOICE') return { ...empty, selected_choices: Array.from(answer.selected) }
  if (answer.kind === 'ORDERING') return { ...empty, selected_choices: answer.order }
  if (answer.kind === 'HOTSPOT') return { ...empty, selected_regions: Array.from(answer.selected) }
  if (answer.kind === 'CATEGORIZE') {
    return {
      ...empty,
      category_placements: Object.entries(answer.placements).map(([itemId, bucketId]) => ({
        item: Number(itemId),
        bucket: bucketId,
      })),
    }
  }
  // MATCHING: only a placement's target id is submitted once it's
  // self-consistently correct (target id === placed item id) — see
  // MatchingAnswer's doc comment for why that's a safe, sufficient signal.
  return {
    ...empty,
    selected_choices: Object.entries(answer.assignments)
      .filter(([targetId, itemId]) => Number(targetId) === itemId)
      .map(([targetId]) => Number(targetId)),
  }
}

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
  const [answers, setAnswers] = useState<Record<number, AnswerState>>({})
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null)
  const [result, setResult] = useState<QuizAttemptResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [certificateId, setCertificateId] = useState<number | null>(null)
  const [isPreparingCertificate, setIsPreparingCertificate] = useState(false)

  const handleSubmit = useCallback(
    async (currentQuiz: QuizDetail, currentAnswers: Record<number, AnswerState>) => {
      setStage('submitting')
      setError(null)
      try {
        const payload = currentQuiz.questions.map((question) => ({
          question: question.id,
          ...buildAnswerPayload(currentAnswers[question.id]),
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
      setAnswers(buildInitialAnswers(detail))
      setRemainingSeconds(detail.time_limit_minutes ? detail.time_limit_minutes * 60 : null)
      setStage('in_progress')
    } catch {
      setError('Could not load the quiz. Please try again.')
      setStage('intro')
    }
  }

  function toggleChoice(question: Question, choiceId: number) {
    setAnswers((prev) => {
      const current = prev[question.id]
      const selected = current?.kind === 'CHOICE' ? new Set(current.selected) : new Set<number>()
      if (question.question_type === 'MULTIPLE_ANSWER') {
        if (selected.has(choiceId)) selected.delete(choiceId)
        else selected.add(choiceId)
      } else {
        selected.clear()
        selected.add(choiceId)
      }
      return { ...prev, [question.id]: { kind: 'CHOICE', selected } }
    })
  }

  function setOrderingAnswer(questionId: number, order: number[]) {
    setAnswers((prev) => ({ ...prev, [questionId]: { kind: 'ORDERING', order } }))
  }

  function setMatchingAnswer(questionId: number, assignments: Record<number, number>) {
    setAnswers((prev) => ({ ...prev, [questionId]: { kind: 'MATCHING', assignments } }))
  }

  function setCategorizeAnswer(questionId: number, placements: Record<number, number>) {
    setAnswers((prev) => ({ ...prev, [questionId]: { kind: 'CATEGORIZE', placements } }))
  }

  function setHotspotAnswer(questionId: number, selected: Set<number>) {
    setAnswers((prev) => ({ ...prev, [questionId]: { kind: 'HOTSPOT', selected } }))
  }

  function getOrderingValue(question: Question): number[] {
    const answer = answers[question.id]
    return answer?.kind === 'ORDERING' ? answer.order : question.choices.map((c) => c.id)
  }

  function getMatchingValue(question: Question): Record<number, number> {
    const answer = answers[question.id]
    return answer?.kind === 'MATCHING' ? answer.assignments : {}
  }

  function getCategorizeValue(question: Question): Record<number, number> {
    const answer = answers[question.id]
    return answer?.kind === 'CATEGORIZE' ? answer.placements : {}
  }

  function getHotspotValue(question: Question): Set<number> {
    const answer = answers[question.id]
    return answer?.kind === 'HOTSPOT' ? answer.selected : new Set()
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
      <Card className="text-center">
        <h2 className="text-base font-semibold text-neutral-900">{quizSummary.title}</h2>
        <p className="mt-2 text-sm text-neutral-500">
          Pass mark: {quizSummary.pass_percentage}%
          {quizSummary.time_limit_minutes && ` · Time limit: ${quizSummary.time_limit_minutes} min`}
          {quizSummary.max_attempts && ` · Max attempts: ${quizSummary.max_attempts}`}
        </p>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <Button className="mt-4" onClick={startQuiz}>
          Start Quiz
        </Button>
      </Card>
    )
  }

  if (stage === 'loading') {
    return <p className="text-sm text-neutral-500">Loading quiz…</p>
  }

  if ((stage === 'in_progress' || stage === 'submitting') && quiz) {
    return (
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-neutral-900">{quiz.title}</h2>
          {remainingSeconds !== null && (
            <span
              className={`rounded-md px-3 py-1 text-sm font-mono font-medium ${
                remainingSeconds <= 60 ? 'bg-red-100 text-red-700' : 'bg-neutral-100 text-neutral-700'
              }`}
            >
              {formatTime(remainingSeconds)}
            </span>
          )}
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <div className="space-y-6">
          {quiz.questions.map((question, index) => (
            <div key={question.id} className="rounded-lg border border-neutral-200 p-4">
              <p className="text-sm font-medium text-neutral-900">
                {index + 1}. {question.question_text}{' '}
                <span className="font-normal text-neutral-400">
                  ({question.points} {question.points === 1 ? 'point' : 'points'})
                </span>
              </p>
              <div className="mt-3">
                {question.question_type === 'ORDERING' ? (
                  <OrderingAnswer
                    items={question.choices.map((c) => ({ id: c.id, text: c.choice_text }))}
                    order={getOrderingValue(question)}
                    onChange={(next) => setOrderingAnswer(question.id, next)}
                  />
                ) : question.question_type === 'MATCHING' ? (
                  <MatchingAnswer
                    items={question.choices.map((c) => ({ id: c.id, text: c.choice_text }))}
                    targets={question.match_targets ?? []}
                    assignments={getMatchingValue(question)}
                    onChange={(next) => setMatchingAnswer(question.id, next)}
                  />
                ) : question.question_type === 'CATEGORIZE' ? (
                  <CategorizeAnswer
                    items={question.categorize_items.map((i) => ({ id: i.id, text: i.item_text, image: i.item_image }))}
                    buckets={question.buckets.map((b) => ({ id: b.id, label: b.label }))}
                    placements={getCategorizeValue(question)}
                    onChange={(next) => setCategorizeAnswer(question.id, next)}
                  />
                ) : question.question_type === 'HOTSPOT' ? (
                  question.image ? (
                    <HotspotAnswer
                      image={question.image}
                      regions={question.hotspot_regions}
                      selected={getHotspotValue(question)}
                      onChange={(next) => setHotspotAnswer(question.id, next)}
                    />
                  ) : (
                    <p className="text-sm text-neutral-400 italic">This question is missing its image.</p>
                  )
                ) : (
                  <div className="space-y-2">
                    {question.choices.map((choice) => {
                      const answer = answers[question.id]
                      const selected = answer?.kind === 'CHOICE' && answer.selected.has(choice.id)
                      return (
                        <label
                          key={choice.id}
                          className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition ${
                            selected ? 'border-brand-navy bg-brand-navy/5' : 'border-neutral-200 hover:bg-neutral-50'
                          }`}
                        >
                          <input
                            type={question.question_type === 'MULTIPLE_ANSWER' ? 'checkbox' : 'radio'}
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
                )}
              </div>
            </div>
          ))}
        </div>

        <Button className="mt-6" disabled={stage === 'submitting'} onClick={() => handleSubmit(quiz, answers)}>
          {stage === 'submitting' ? 'Submitting…' : 'Submit'}
        </Button>
      </Card>
    )
  }

  if (stage === 'results' && result && quiz) {
    const canRetake = !result.passed && (quiz.max_attempts === null || result.attempt_number < quiz.max_attempts)

    return (
      <Card>
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
              <div key={question.id} className="rounded-lg border border-neutral-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <p className="text-sm font-medium text-neutral-900">{question.question_text}</p>
                  <span
                    className={`shrink-0 text-xs font-medium ${
                      answer?.is_correct ? 'text-emerald-600' : 'text-red-600'
                    }`}
                  >
                    {answer?.is_correct ? 'Correct' : 'Incorrect'}
                  </span>
                </div>
                {question.question_type === 'ORDERING' ? (
                  <ol className="mt-2 space-y-1">
                    {getOrderingValue(question).map((id, i) => {
                      const item = question.choices.find((c) => c.id === id)
                      return (
                        <li key={id} className="flex items-center gap-2 text-sm text-neutral-700">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-100 text-xs font-medium text-neutral-500">
                            {i + 1}
                          </span>
                          {item?.choice_text}
                        </li>
                      )
                    })}
                  </ol>
                ) : question.question_type === 'MATCHING' ? (
                  <ul className="mt-2 space-y-1">
                    {question.choices.map((choice) => {
                      const assignments = getMatchingValue(question)
                      const placedTargetId = Object.entries(assignments).find(([, itemId]) => itemId === choice.id)?.[0]
                      const isCorrect = placedTargetId !== undefined && Number(placedTargetId) === choice.id
                      const placedTarget =
                        placedTargetId !== undefined
                          ? question.match_targets?.find((t) => t.id === Number(placedTargetId))
                          : undefined
                      const correctTarget = question.match_targets?.find((t) => t.id === choice.id)
                      return (
                        <li
                          key={choice.id}
                          className={`text-sm ${isCorrect ? 'font-medium text-emerald-700' : 'text-neutral-700'}`}
                        >
                          {choice.choice_text} →{' '}
                          {placedTarget ? placedTarget.text : <span className="italic text-neutral-400">not placed</span>}
                          {!isCorrect && correctTarget && <span className="ml-1 text-emerald-700">(correct: {correctTarget.text})</span>}
                        </li>
                      )
                    })}
                  </ul>
                ) : question.question_type === 'CATEGORIZE' ? (
                  <ul className="mt-2 space-y-1">
                    {question.categorize_items.map((item) => {
                      const placedBucketId = answer?.category_placements[String(item.id)]
                      const correctBucketId = answer?.correct_placements?.[String(item.id)]
                      const isCorrect = placedBucketId !== undefined && placedBucketId === correctBucketId
                      const placedBucket = question.buckets.find((b) => b.id === placedBucketId)
                      const correctBucket = question.buckets.find((b) => b.id === correctBucketId)
                      return (
                        <li
                          key={item.id}
                          className={`text-sm ${isCorrect ? 'font-medium text-emerald-700' : 'text-neutral-700'}`}
                        >
                          {item.item_text} →{' '}
                          {placedBucket ? placedBucket.label : <span className="italic text-neutral-400">not placed</span>}
                          {!isCorrect && correctBucket && <span className="ml-1 text-emerald-700">(correct: {correctBucket.label})</span>}
                        </li>
                      )
                    })}
                  </ul>
                ) : question.question_type === 'HOTSPOT' ? (
                  question.image && (
                    <div className="relative mt-2 inline-block max-w-full">
                      <img src={question.image} alt="" className="block max-w-full rounded border border-neutral-200" />
                      {question.hotspot_regions.map((region) => {
                        const wasSelected = answer?.selected_regions.includes(region.id) ?? false
                        const knownCorrect = answer?.correct_region_ids.includes(region.id) ?? false
                        return (
                          <div
                            key={region.id}
                            className={`absolute rounded-sm border-2 ${
                              knownCorrect ? 'border-emerald-500' : wasSelected ? 'border-red-500' : 'border-transparent'
                            }`}
                            style={{
                              left: `${region.x}%`,
                              top: `${region.y}%`,
                              width: `${region.width}%`,
                              height: `${region.height}%`,
                            }}
                          >
                            {wasSelected && (
                              <span
                                className={`absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full text-xs text-white shadow ${
                                  knownCorrect ? 'bg-emerald-600' : 'bg-red-600'
                                }`}
                              >
                                {knownCorrect ? '✓' : '✕'}
                              </span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )
                ) : (
                  <ul className="mt-2 space-y-1">
                    {question.choices.map((choice) => {
                      const wasSelected = answer?.selected_choices.includes(choice.id) ?? false
                      // The quiz itself never sends choice.is_correct to a learner (it
                      // would leak the answer key while the quiz is in progress). Once
                      // there's a result, the attempt's own answer carries the correct
                      // choice ids for this question instead — safe to show now.
                      const knownCorrect = answer?.correct_choice_ids.includes(choice.id) ?? false
                      return (
                        <li
                          key={choice.id}
                          className={`text-sm ${
                            knownCorrect
                              ? 'font-medium text-emerald-700'
                              : wasSelected
                                ? 'text-neutral-900'
                                : 'text-neutral-500'
                          }`}
                        >
                          {wasSelected ? '●' : '○'} {choice.choice_text}
                          {knownCorrect && ' (correct answer)'}
                        </li>
                      )
                    })}
                  </ul>
                )}

                {answer?.explanation && (
                  <div
                    className="mt-3 rounded-md bg-neutral-50 p-3 text-sm text-neutral-700"
                    dangerouslySetInnerHTML={{ __html: answer.explanation }}
                  />
                )}

                {answer?.is_correct && answer.feedback_correct && (
                  <p className="mt-2 text-sm text-emerald-700">{answer.feedback_correct}</p>
                )}
                {answer && !answer.is_correct && answer.feedback_incorrect && (
                  <p className="mt-2 text-sm text-red-700">{answer.feedback_incorrect}</p>
                )}
              </div>
            )
          })}
        </div>

        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        <div className="mt-6 flex gap-3">
          {canRetake && (
            <Button variant="outline" onClick={() => setStage('intro')}>
              Retake Quiz
            </Button>
          )}
          {result.passed && (
            <Button disabled={isPreparingCertificate} onClick={handleDownloadCertificate}>
              {isPreparingCertificate ? 'Preparing…' : 'Download Certificate'}
            </Button>
          )}
        </div>
      </Card>
    )
  }

  return null
}
