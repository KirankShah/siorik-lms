import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { CertificateButton } from '../components/CertificateButton'
import { CourseSidebar } from '../components/player/CourseSidebar'
import { PagePlayer } from '../components/player/PagePlayer'
import { enrollInCourse, fetchCourseDetail, fetchEnrollments } from '../lib/coursesApi'
import { computeUnlockedPageIds, flattenCoursePages } from '../lib/pageSequence'
import type { CourseDetail, Enrollment } from '../types/courses'

export function CourseDetailPage() {
  const { id: slug } = useParams<{ id: string }>()

  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [activePageId, setActivePageId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isEnrolling, setIsEnrolling] = useState(false)
  const [hasPositionedInitially, setHasPositionedInitially] = useState(false)

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

  const entries = useMemo(() => (course ? flattenCoursePages(course) : []), [course])

  const completedPageIds = useMemo(
    () => new Set(enrollment?.page_progress.filter((p) => p.completed_at).map((p) => p.page) ?? []),
    [enrollment],
  )

  const { unlocked, frontierPageId } = useMemo(
    () => computeUnlockedPageIds(entries, completedPageIds),
    [entries, completedPageIds],
  )

  // Resume where they left off, once, after the first load.
  useEffect(() => {
    if (!hasPositionedInitially && entries.length > 0) {
      setActivePageId(frontierPageId)
      setHasPositionedInitially(true)
    }
  }, [hasPositionedInitially, entries, frontierPageId])

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

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!course) return <p className="text-sm text-slate-500">Loading course…</p>

  const activeIndex = entries.findIndex((e) => e.page.id === activePageId)
  const activeEntry = activeIndex >= 0 ? entries[activeIndex] : null
  const allPagesComplete = entries.length > 0 && entries.every((e) => completedPageIds.has(e.page.id))

  function goToOffset(offset: number) {
    const target = entries[activeIndex + offset]
    if (target) setActivePageId(target.page.id)
  }

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <aside className="shrink-0 lg:w-72">
        <CourseSidebar
          course={course}
          entries={entries}
          enrollment={enrollment}
          activePageId={activePageId}
          unlockedPageIds={unlocked}
          onSelectPage={setActivePageId}
        />
      </aside>

      <div className="flex-1">
        {!enrollment ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
            <p className="text-sm text-slate-600">Enroll to start this course and track your progress.</p>
            <button
              type="button"
              disabled={isEnrolling}
              onClick={() => void handleEnroll()}
              className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isEnrolling ? 'Enrolling…' : 'Enroll'}
            </button>
          </div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-slate-500">This course has no content yet.</p>
        ) : activeEntry ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="mb-1 text-xs text-slate-400">
              {activeEntry.module.title} / {activeEntry.lesson.title}
            </p>
            <PagePlayer
              key={activeEntry.page.id}
              page={activeEntry.page}
              courseId={course.id}
              enrollmentId={enrollment.id}
              existingProgress={enrollment.page_progress.find((p) => p.page === activeEntry.page.id)}
              hasPrevious={activeIndex > 0}
              hasNext={activeIndex < entries.length - 1}
              onPrevious={() => goToOffset(-1)}
              onNext={() => goToOffset(1)}
              onProgressSynced={setEnrollment}
            />

            {allPagesComplete && (
              <div className="mt-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-sm font-medium text-emerald-800">You've completed every page in this course.</p>
                <div className="mt-3">
                  <CertificateButton courseId={course.id} />
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Select a page to get started.</p>
        )}
      </div>
    </div>
  )
}
