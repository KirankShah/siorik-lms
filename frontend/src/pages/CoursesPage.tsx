import { useEffect, useState } from 'react'
import { Check, Lock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ProgressBar } from '../components/ProgressBar'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { enrollInCourse, fetchCourses, fetchEnrollments } from '../lib/coursesApi'
import type { CourseListItem, Enrollment } from '../types/courses'

const DEMO_LOCKED_MESSAGE = 'Locked — contact admin for access'
// This card only ever renders for path_state === 'locked', which the
// backend only ever returns for a course the learner hasn't reached yet in
// their own Learning Path — see courses.permissions.path_accessible_courses_for_user.
const PATH_LOCKED_MESSAGE = "Locked — complete the earlier courses in your Learning Path first"

export function CoursesPage() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState<CourseListItem[] | null>(null)
  const [enrollmentByCourse, setEnrollmentByCourse] = useState<Map<number, Enrollment>>(new Map())
  const [error, setError] = useState<string | null>(null)
  const [enrollingCourseId, setEnrollingCourseId] = useState<number | null>(null)
  const [lockedNoticeCourseId, setLockedNoticeCourseId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [courseList, enrollments] = await Promise.all([fetchCourses(), fetchEnrollments()])
        if (cancelled) return
        setCourses(courseList)
        setEnrollmentByCourse(new Map(enrollments.map((enrollment) => [enrollment.course, enrollment])))
      } catch {
        if (!cancelled) setError('Could not load courses.')
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleEnroll(course: CourseListItem) {
    setEnrollingCourseId(course.id)
    try {
      const enrollment = await enrollInCourse(course.id)
      setEnrollmentByCourse((prev) => new Map(prev).set(course.id, enrollment))
      navigate(`/courses/${course.slug}`)
    } catch {
      setError('Could not enroll in this course. Please try again.')
      setEnrollingCourseId(null)
    }
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (!courses) {
    return <p className="text-sm text-neutral-500">Loading courses…</p>
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Courses</h1>

      {courses.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">No courses are available yet.</p>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => {
            if (course.is_locked || course.path_state === 'locked') {
              return (
                <LockedCourseCard
                  key={course.id}
                  course={course}
                  message={course.is_locked ? DEMO_LOCKED_MESSAGE : PATH_LOCKED_MESSAGE}
                  showNotice={lockedNoticeCourseId === course.id}
                  onToggleNotice={() =>
                    setLockedNoticeCourseId((prev) => (prev === course.id ? null : course.id))
                  }
                />
              )
            }

            const enrollment = enrollmentByCourse.get(course.id)
            return (
              <Card key={course.id} className="flex flex-col overflow-hidden p-0 transition hover:shadow-md">
                <button
                  type="button"
                  onClick={() => navigate(`/courses/${course.slug}`)}
                  className="relative aspect-video w-full bg-neutral-100 text-left"
                >
                  {course.path_state && (
                    <span
                      className={`absolute right-2 top-2 z-10 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium shadow-sm ${
                        course.path_state === 'completed'
                          ? 'bg-teal-600 text-white'
                          : 'bg-brand-navy text-white'
                      }`}
                    >
                      {course.path_state === 'completed' ? (
                        <>
                          <Check className="h-3 w-3" /> Completed
                        </>
                      ) : (
                        'Up Next'
                      )}
                    </span>
                  )}
                  {course.cover_image ? (
                    <img
                      src={course.cover_image}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-brand-navy to-brand-navy-light text-white/40">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={1.5}
                        className="h-10 w-10"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
                        />
                      </svg>
                    </div>
                  )}
                </button>

                <div className="flex flex-1 flex-col p-4">
                  <button
                    type="button"
                    onClick={() => navigate(`/courses/${course.slug}`)}
                    className="text-left text-sm font-semibold text-neutral-900 hover:underline"
                  >
                    {course.title}
                  </button>
                  <p className="mt-1 line-clamp-2 flex-1 text-xs text-neutral-500">
                    {course.description || 'No description provided.'}
                  </p>

                  <div className="mt-4">
                    {enrollment ? (
                      <div className="space-y-2">
                        <ProgressBar percent={enrollment.progress_percent} label="Your progress" />
                        <Button onClick={() => navigate(`/courses/${course.slug}`)} size="sm" className="w-full">
                          Continue
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={enrollingCourseId === course.id}
                        onClick={() => handleEnroll(course)}
                        className="w-full"
                      >
                        {enrollingCourseId === course.id ? 'Enrolling…' : 'Enroll'}
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

// Rendered for a demo user viewing a course outside their org's assignment
// (CourseListItem.is_locked), or a course the learner hasn't reached yet in
// their own Learning Path (path_state === 'locked') — either way, a teaser
// only. It never links anywhere: the backend denies retrieval/enrollment for
// this course regardless (visible_courses_for_user / path_accessible_courses_for_user),
// so there's nothing for a click here to navigate to.
function LockedCourseCard({
  course,
  message,
  showNotice,
  onToggleNotice,
}: {
  course: CourseListItem
  message: string
  showNotice: boolean
  onToggleNotice: () => void
}) {
  return (
    <Card className="flex flex-col overflow-hidden p-0">
      <button
        type="button"
        onClick={onToggleNotice}
        title={message}
        className="group relative aspect-video w-full cursor-not-allowed bg-neutral-100 text-left"
      >
        {course.cover_image ? (
          <img src={course.cover_image} alt="" className="h-full w-full object-cover opacity-50 grayscale" />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-neutral-200 text-neutral-400">
            <Lock className="h-10 w-10" />
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center bg-neutral-900/0 transition group-hover:bg-neutral-900/40">
          <Lock className="h-8 w-8 text-white opacity-0 transition group-hover:opacity-100" />
        </div>
      </button>

      <div className="flex flex-1 flex-col p-4">
        <button
          type="button"
          onClick={onToggleNotice}
          title={message}
          className="flex items-center gap-1.5 text-left text-sm font-semibold text-neutral-400"
        >
          <Lock className="h-3.5 w-3.5 shrink-0" />
          {course.title}
        </button>
        <p className="mt-1 line-clamp-2 flex-1 text-xs text-neutral-400">
          {course.description || 'No description provided.'}
        </p>

        <div className="mt-4">
          <Badge variant="neutral" className="w-full justify-center py-2 text-neutral-500">
            Locked
          </Badge>
          {showNotice && <p className="mt-2 text-xs text-neutral-500">{message}</p>}
        </div>
      </div>
    </Card>
  )
}
