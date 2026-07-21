import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ProgressBar } from '../components/ProgressBar'
import { completeLesson, enrollInCourse, fetchCourseDetail, fetchEnrollments } from '../lib/coursesApi'
import type { CourseDetail, Enrollment, Lesson } from '../types/courses'

function CheckIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
      <path
        fillRule="evenodd"
        d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
        clipRule="evenodd"
      />
    </svg>
  )
}

function LessonContent({ lesson }: { lesson: Lesson }) {
  const source = lesson.content_file || lesson.content_url

  if (lesson.lesson_type === 'VIDEO') {
    if (!source) return <EmptyContent />
    return (
      // eslint-disable-next-line jsx-a11y/media-has-caption
      <video key={lesson.id} controls className="aspect-video w-full rounded-lg bg-black">
        <source src={source} />
      </video>
    )
  }

  if (lesson.lesson_type === 'SLIDES' || lesson.lesson_type === 'DOCUMENT') {
    if (!source) return <EmptyContent />
    // Renders inline for PDFs; browsers will typically prompt a download for
    // pptx/docx instead of rendering them — a richer viewer is a future improvement.
    return (
      <iframe
        key={lesson.id}
        src={source}
        title={lesson.title}
        className="h-[70vh] w-full rounded-lg border border-slate-200 bg-white"
      />
    )
  }

  // TEXT lessons: the Lesson model has no dedicated text body field yet, only
  // an optional file/URL, so we surface whichever is present as a fallback.
  if (lesson.content_url) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-700">
        <a href={lesson.content_url} target="_blank" rel="noreferrer" className="text-slate-900 underline">
          {lesson.content_url}
        </a>
      </div>
    )
  }

  return <EmptyContent />
}

function EmptyContent() {
  return (
    <div className="flex h-[70vh] items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-400">
      No content has been added for this lesson yet.
    </div>
  )
}

export function CourseDetailPage() {
  const { id: slug } = useParams<{ id: string }>()

  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null)
  const [activeLessonId, setActiveLessonId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isEnrolling, setIsEnrolling] = useState(false)
  const [isMarkingComplete, setIsMarkingComplete] = useState(false)

  useEffect(() => {
    if (!slug) return
    let cancelled = false

    async function load() {
      try {
        const courseDetail = await fetchCourseDetail(slug!)
        if (cancelled) return
        setCourse(courseDetail)
        setActiveLessonId(courseDetail.modules[0]?.lessons[0]?.id ?? null)

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

  const lessons = useMemo(
    () => course?.modules.flatMap((module) => module.lessons) ?? [],
    [course],
  )
  const activeLesson = lessons.find((lesson) => lesson.id === activeLessonId) ?? null
  const completedLessonIds = useMemo(
    () => new Set(enrollment?.completed_lesson_ids ?? []),
    [enrollment],
  )

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

  async function handleMarkComplete() {
    if (!enrollment || !activeLesson) return
    setIsMarkingComplete(true)
    try {
      const updated = await completeLesson(enrollment.id, activeLesson.id)
      setEnrollment(updated)
    } catch {
      setError('Could not update your progress. Please try again.')
    } finally {
      setIsMarkingComplete(false)
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!course) return <p className="text-sm text-slate-500">Loading course…</p>

  const isActiveLessonComplete = activeLesson ? completedLessonIds.has(activeLesson.id) : false

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <aside className="shrink-0 lg:w-72">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h1 className="text-sm font-semibold text-slate-900">{course.title}</h1>
          <div className="mt-3">
            <ProgressBar percent={enrollment?.progress_percent ?? 0} label="Course progress" />
          </div>

          <nav className="mt-4 space-y-4">
            {course.modules.map((module) => (
              <div key={module.id}>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {module.title}
                </p>
                <ul className="space-y-0.5">
                  {module.lessons.map((lesson) => {
                    const isComplete = completedLessonIds.has(lesson.id)
                    const isActive = lesson.id === activeLessonId
                    return (
                      <li key={lesson.id}>
                        <button
                          type="button"
                          onClick={() => setActiveLessonId(lesson.id)}
                          className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition ${
                            isActive ? 'bg-slate-100 text-slate-900' : 'text-slate-600 hover:bg-slate-50'
                          }`}
                        >
                          <span
                            className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
                              isComplete ? 'bg-emerald-500 text-white' : 'border border-slate-300'
                            }`}
                          >
                            {isComplete && <CheckIcon />}
                          </span>
                          <span className="line-clamp-1">{lesson.title}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </div>
      </aside>

      <div className="flex-1">
        {!enrollment && (
          <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span>Enroll to track your progress and mark lessons complete.</span>
            <button
              type="button"
              disabled={isEnrolling}
              onClick={handleEnroll}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isEnrolling ? 'Enrolling…' : 'Enroll'}
            </button>
          </div>
        )}

        {activeLesson ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-900">{activeLesson.title}</h2>
                <p className="text-xs text-slate-500">{activeLesson.estimated_minutes} min</p>
              </div>
              <button
                type="button"
                disabled={!enrollment || isMarkingComplete || isActiveLessonComplete}
                onClick={handleMarkComplete}
                className={`rounded-md px-3 py-2 text-xs font-medium transition disabled:cursor-not-allowed ${
                  isActiveLessonComplete
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-60'
                }`}
              >
                {isActiveLessonComplete ? 'Completed ✓' : isMarkingComplete ? 'Saving…' : 'Mark complete'}
              </button>
            </div>

            <LessonContent lesson={activeLesson} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">This course has no lessons yet.</p>
        )}
      </div>
    </div>
  )
}
