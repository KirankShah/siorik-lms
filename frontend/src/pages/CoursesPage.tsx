import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ProgressBar } from '../components/ProgressBar'
import { enrollInCourse, fetchCourses, fetchEnrollments } from '../lib/coursesApi'
import type { CourseListItem, Enrollment } from '../types/courses'

export function CoursesPage() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState<CourseListItem[] | null>(null)
  const [enrollmentByCourse, setEnrollmentByCourse] = useState<Map<number, Enrollment>>(new Map())
  const [error, setError] = useState<string | null>(null)
  const [enrollingCourseId, setEnrollingCourseId] = useState<number | null>(null)

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
    return <p className="text-sm text-slate-500">Loading courses…</p>
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-slate-900">Courses</h1>

      {courses.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">No courses are available yet.</p>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => {
            const enrollment = enrollmentByCourse.get(course.id)
            return (
              <div
                key={course.id}
                className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md"
              >
                <button
                  type="button"
                  onClick={() => navigate(`/courses/${course.slug}`)}
                  className="aspect-video w-full bg-slate-100 text-left"
                >
                  {course.cover_image ? (
                    <img
                      src={course.cover_image}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-slate-200 to-slate-100 text-slate-400">
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
                    className="text-left text-sm font-semibold text-slate-900 hover:underline"
                  >
                    {course.title}
                  </button>
                  <p className="mt-1 line-clamp-2 flex-1 text-xs text-slate-500">
                    {course.description || 'No description provided.'}
                  </p>

                  <div className="mt-4">
                    {enrollment ? (
                      <div className="space-y-2">
                        <ProgressBar percent={enrollment.progress_percent} label="Your progress" />
                        <button
                          type="button"
                          onClick={() => navigate(`/courses/${course.slug}`)}
                          className="w-full rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800"
                        >
                          Continue
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        disabled={enrollingCourseId === course.id}
                        onClick={() => handleEnroll(course)}
                        className="w-full rounded-md border border-slate-900 px-3 py-2 text-xs font-medium text-slate-900 transition hover:bg-slate-900 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {enrollingCourseId === course.id ? 'Enrolling…' : 'Enroll'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
