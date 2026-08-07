import { useEffect, useRef, useState } from 'react'
import { AssignmentSlidePlayer } from './AssignmentSlidePlayer'
import { ContentProtectionBoundary } from './ContentProtectionBoundary'
import { ContentSlidePlayer } from './ContentSlidePlayer'
import { QuizSlidePlayer } from './QuizSlidePlayer'
import { ScenarioSlidePlayer } from './ScenarioSlidePlayer'
import { saveSlideProgress } from '../../lib/coursesApi'
import type { Enrollment } from '../../types/courses'
import type { SlideProgress, SlideSummary } from '../../types/slides'

// How often accumulated dwell time is flushed to the server, in local ticks
// (the ticker itself runs every 1s so the Next-button gate updates smoothly;
// this just throttles the network round-trips).
const FLUSH_EVERY_N_TICKS = 10

interface SlidePlayerProps {
  slide: SlideSummary
  courseId: number
  courseTemplateId: number | null
  enrollmentId: number
  existingProgress: SlideProgress | undefined
  onProgressSynced: (enrollment: Enrollment) => void
  onCanAdvanceChange: (canAdvance: boolean, secondsRemaining: number) => void
  onEnterFullscreen?: () => void
  isFullscreen?: boolean
}

export function SlidePlayer({
  slide,
  courseId,
  courseTemplateId,
  enrollmentId,
  existingProgress,
  onProgressSynced,
  onCanAdvanceChange,
  onEnterFullscreen,
  isFullscreen,
}: SlidePlayerProps) {
  const [dwellSeconds, setDwellSeconds] = useState(existingProgress?.time_spent_seconds ?? 0)
  const [isMarkedComplete, setIsMarkedComplete] = useState(!!existingProgress?.completed_at)
  const unsyncedRef = useRef(0)
  const completeSentRef = useRef(!!existingProgress?.completed_at)

  async function flush(markCompleted: boolean) {
    const delta = unsyncedRef.current
    if (delta === 0 && !markCompleted) return
    unsyncedRef.current = 0
    try {
      const enrollment = await saveSlideProgress(enrollmentId, {
        slide: slide.id,
        time_spent_seconds: delta,
        ...(markCompleted ? { completed: true } : {}),
      })
      onProgressSynced(enrollment)
      if (markCompleted) {
        setIsMarkedComplete(true)
        completeSentRef.current = true
      }
    } catch {
      unsyncedRef.current += delta // retry on the next tick
    }
  }

  // Reset per-slide state and start the dwell ticker whenever the slide changes.
  useEffect(() => {
    setDwellSeconds(existingProgress?.time_spent_seconds ?? 0)
    setIsMarkedComplete(!!existingProgress?.completed_at)
    completeSentRef.current = !!existingProgress?.completed_at
    unsyncedRef.current = 0

    let tickCount = 0
    const interval = setInterval(() => {
      if (document.hidden) return
      setDwellSeconds((seconds) => seconds + 1)
      unsyncedRef.current += 1
      tickCount += 1
      if (tickCount % FLUSH_EVERY_N_TICKS === 0) void flush(false)
    }, 1000)

    return () => {
      clearInterval(interval)
      void flush(false)
    }
    // Deliberately re-runs only when the slide changes — existingProgress is
    // just the seed value for this run, re-reading it on every render would
    // fight the ticker's own state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slide.id])

  const requiredSeconds = slide.estimated_minutes * 60
  const dwellSatisfied = requiredSeconds === 0 || dwellSeconds >= requiredSeconds

  // CONTENT slides auto-complete once the dwell requirement is met; QUIZ/
  // ASSIGNMENT/SCENARIO slides only complete via explicit submission
  // (handleSubmitted).
  useEffect(() => {
    if (slide.slide_type === 'CONTENT' && dwellSatisfied && !completeSentRef.current) {
      void flush(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dwellSatisfied, slide.slide_type])

  const canAdvance = slide.slide_type === 'CONTENT' ? dwellSatisfied || isMarkedComplete : isMarkedComplete

  useEffect(() => {
    onCanAdvanceChange(canAdvance, Math.max(0, requiredSeconds - dwellSeconds))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAdvance, dwellSeconds, requiredSeconds])

  function handleSubmitted() {
    void flush(true)
  }

  let content
  if (slide.slide_type === 'QUIZ') {
    content = <QuizSlidePlayer slide={slide} courseId={courseId} onSubmitted={handleSubmitted} />
  } else if (slide.slide_type === 'ASSIGNMENT') {
    content = <AssignmentSlidePlayer slide={slide} onSubmitted={handleSubmitted} />
  } else if (slide.slide_type === 'SCENARIO') {
    content = <ScenarioSlidePlayer slide={slide} onSubmitted={handleSubmitted} />
  } else {
    content = (
      <ContentSlidePlayer
        slide={slide}
        courseTemplateId={courseTemplateId}
        onEnterFullscreen={onEnterFullscreen}
        isFullscreen={isFullscreen}
      />
    )
  }

  return <ContentProtectionBoundary>{content}</ContentProtectionBoundary>
}
