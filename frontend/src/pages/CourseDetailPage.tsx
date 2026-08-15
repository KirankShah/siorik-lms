import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CourseCompletionModal } from '../components/CourseCompletionModal'
import { CourseSidebar } from '../components/player/CourseSidebar'
import { FullscreenSlideOverlay } from '../components/player/FullscreenSlideOverlay'
import { SlideNavFooter } from '../components/player/SlideNavFooter'
import { SlidePlayer } from '../components/player/SlidePlayer'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { enrollInCourse, fetchCourseDetail, fetchEnrollments, retakeCourse } from '../lib/coursesApi'
import { computeReachedSlideIds, flattenCourseSlides } from '../lib/slideSequence'
import type { CourseDetail, Enrollment } from '../types/courses'

export function CourseDetailPage() {
  const { id: slug } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [activeSlideId, setActiveSlideId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isEnrolling, setIsEnrolling] = useState(false)
  const [hasPositionedInitially, setHasPositionedInitially] = useState(false)
  const [canAdvance, setCanAdvance] = useState(false)
  const [secondsRemaining, setSecondsRemaining] = useState(0)
  const [nextDisabledReason, setNextDisabledReason] = useState<string | undefined>(undefined)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showCompletionModal, setShowCompletionModal] = useState(false)
  const [isRetaking, setIsRetaking] = useState(false)

  useEffect(() => {
    if (!slug) return
    let cancelled = false

    async function load() {
      try {
        const courseDetail = await fetchCourseDetail(slug!)
        if (cancelled) return
        setCourse(courseDetail)

        const enrollments = await fetchEnrollments(courseDetail.id)
        if (cancelled) return
        setEnrollment(enrollments[0] ?? null)
      } catch {
        if (!cancelled) setError('Could not load this course.')
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [slug])

  const entries = useMemo(() => (course ? flattenCourseSlides(course) : []), [course])

  const completedSlideIds = useMemo(
    () => new Set(enrollment?.slide_progress.filter((p) => p.completed_at).map((p) => p.slide) ?? []),
    [enrollment],
  )

  const reachedSlideIds = useMemo(() => computeReachedSlideIds(entries, completedSlideIds), [entries, completedSlideIds])

  const allSlidesComplete = entries.length > 0 && entries.every((e) => completedSlideIds.has(e.slide.id))

  // Shown once whenever the learner reaches (or revisits) a fully-completed
  // course — dismissing it doesn't reopen it again this mount, since
  // allSlidesComplete can't flip back to false once every slide is done.
  useEffect(() => {
    if (allSlidesComplete) setShowCompletionModal(true)
  }, [allSlidesComplete])

  // Resume where they left off, once, after the first load — the first slide
  // not yet completed, or the last slide if the whole course is done.
  useEffect(() => {
    if (!hasPositionedInitially && entries.length > 0) {
      const resumeEntry = entries.find((e) => !completedSlideIds.has(e.slide.id)) ?? entries[entries.length - 1]
      setActiveSlideId(resumeEntry.slide.id)
      setHasPositionedInitially(true)
    }
  }, [hasPositionedInitially, entries, completedSlideIds])

  // Assume a fresh slide isn't advanceable until its own SlidePlayer reports
  // otherwise — avoids a flash of the previous slide's gate state.
  useEffect(() => {
    setCanAdvance(false)
    setSecondsRemaining(0)
    setNextDisabledReason(undefined)
  }, [activeSlideId])

  async function handleEnroll() {
    if (!course) return
    setIsEnrolling(true)
    try {
      const newEnrollment = await enrollInCourse(course.id)
      setEnrollment(newEnrollment)
    } catch {
      setError('Could not enroll in this course. Please try again.')
    } finally {
      setIsEnrolling(false)
    }
  }

  // Resets progress/attempts server-side (courses.views.EnrollmentViewSet.retake)
  // before navigating back to slide 1, so the fresh enrollment (empty
  // slide_progress) is already in state by the time the player re-renders —
  // otherwise completedSlideIds would still reflect the old, now-deleted
  // progress until the next unrelated re-fetch.
  async function handleRetake() {
    if (!enrollment) return
    setIsRetaking(true)
    try {
      const freshEnrollment = await retakeCourse(enrollment.id)
      setEnrollment(freshEnrollment)
      setShowCompletionModal(false)
      goToFirst()
    } catch {
      setError('Could not reset your progress for a retake. Please try again.')
    } finally {
      setIsRetaking(false)
    }
  }

  const activeIndex = entries.findIndex((e) => e.slide.id === activeSlideId)
  const activeEntry = activeIndex >= 0 ? entries[activeIndex] : null

  // The frontier a learner can jump to via "Go to last slide" — the furthest
  // reached entry, never a locked one.
  const lastReachedIndex = (() => {
    let idx = -1
    entries.forEach((e, i) => {
      if (reachedSlideIds.has(e.slide.id)) idx = i
    })
    return idx
  })()

  function goToOffset(offset: number) {
    const target = entries[activeIndex + offset]
    if (target) setActiveSlideId(target.slide.id)
  }

  function goToFirst() {
    if (entries.length > 0) setActiveSlideId(entries[0].slide.id)
  }

  function goToLastReached() {
    if (lastReachedIndex >= 0) setActiveSlideId(entries[lastReachedIndex].slide.id)
  }

  // Escape/arrow-key controls for fullscreen mode — mirrors the on-screen
  // Previous/Next buttons, including the dwell-time gate on advancing.
  useEffect(() => {
    if (!isFullscreen) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setIsFullscreen(false)
      } else if (e.key === 'ArrowLeft' && activeIndex > 0) {
        goToOffset(-1)
      } else if (e.key === 'ArrowRight' && activeIndex < entries.length - 1 && canAdvance) {
        goToOffset(1)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFullscreen, activeIndex, entries.length, canAdvance])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!course) return <p className="text-sm text-neutral-500">Loading course…</p>

  const lessonEntries = activeEntry ? entries.filter((e) => e.lesson.id === activeEntry.lesson.id) : []
  const lessonCompletedCount = lessonEntries.filter((e) => completedSlideIds.has(e.slide.id)).length

  const slidePlayerNode = activeEntry && enrollment && (
    <SlidePlayer
      key={activeEntry.slide.id}
      slide={activeEntry.slide}
      courseTemplateId={course.template}
      enrollmentId={enrollment.id}
      existingProgress={enrollment.slide_progress.find((p) => p.slide === activeEntry.slide.id)}
      onProgressSynced={setEnrollment}
      onCanAdvanceChange={(advance, remaining, disabledReason) => {
        setCanAdvance(advance)
        setSecondsRemaining(remaining)
        setNextDisabledReason(disabledReason)
      }}
      onEnterFullscreen={() => setIsFullscreen(true)}
      isFullscreen={isFullscreen}
    />
  )

  // Rendered from both the fullscreen and normal return branches below —
  // FullscreenSlideOverlay returns its own tree early, so this can't just
  // live once at the bottom of the normal branch's JSX or it would never
  // appear while fullscreen (the bug this comment is here to prevent
  // regressing: the modal silently never showed in fullscreen mode).
  const completionModalNode = showCompletionModal && enrollment && (
    <CourseCompletionModal
      courseName={course.title}
      courseId={course.id}
      isEligible={!enrollment.certificate_ineligible_reason}
      isRetaking={isRetaking}
      onRetake={() => void handleRetake()}
      onBackToCourse={() => setShowCompletionModal(false)}
      onMaybeLater={() => {
        setShowCompletionModal(false)
        navigate('/dashboard')
      }}
      onCertificateDownloaded={() => {
        setShowCompletionModal(false)
        navigate('/dashboard')
      }}
    />
  )

  if (isFullscreen && activeEntry && enrollment) {
    return (
      <>
        <FullscreenSlideOverlay
          activeEntry={activeEntry}
          isCanvasSlide={activeEntry.slide.slide_type === 'CONTENT'}
          hasPrevious={activeIndex > 0}
          hasNext={activeIndex < entries.length - 1}
          onPrevious={() => goToOffset(-1)}
          onNext={() => goToOffset(1)}
          nextDisabled={!canAdvance}
          secondsRemaining={secondsRemaining}
          nextDisabledReason={nextDisabledReason}
          isAtFirst={activeIndex <= 0}
          isAtLast={activeIndex >= lastReachedIndex}
          onGoToFirst={goToFirst}
          onGoToLast={goToLastReached}
          onExit={() => setIsFullscreen(false)}
        >
          {slidePlayerNode}
        </FullscreenSlideOverlay>
        {completionModalNode}
      </>
    )
  }

  return (
    <div className="flex flex-col items-start gap-6 lg:flex-row">
      <aside className="no-print shrink-0 lg:w-72">
        <CourseSidebar
          course={course}
          entries={entries}
          enrollment={enrollment}
          activeSlideId={activeSlideId}
          reachedSlideIds={reachedSlideIds}
          onSelectSlide={setActiveSlideId}
        />
      </aside>

      <div className="flex-1">
        {!enrollment ? (
          <Card className="text-center">
            <p className="text-sm text-neutral-600">Enroll to start this course and track your progress.</p>
            <Button className="mt-4" disabled={isEnrolling} onClick={() => void handleEnroll()}>
              {isEnrolling ? 'Enrolling…' : 'Enroll'}
            </Button>
          </Card>
        ) : entries.length === 0 ? (
          <p className="text-sm text-neutral-500">This course has no content yet.</p>
        ) : activeEntry ? (
          <Card>
            <div className="no-print mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-neutral-400">
                {activeEntry.module.title} / {activeEntry.lesson.title}
              </p>
              <p className="text-xs text-neutral-400">
                {lessonCompletedCount} of {lessonEntries.length} slides complete in this lesson
              </p>
            </div>

            {slidePlayerNode}

            <SlideNavFooter
              hasPrevious={activeIndex > 0}
              hasNext={activeIndex < entries.length - 1}
              onPrevious={() => goToOffset(-1)}
              onNext={() => goToOffset(1)}
              nextDisabled={!canAdvance}
              secondsRemaining={secondsRemaining}
              nextDisabledReason={nextDisabledReason}
            />

            {completionModalNode}
          </Card>
        ) : (
          <p className="text-sm text-neutral-500">Select a slide to get started.</p>
        )}
      </div>
    </div>
  )
}
