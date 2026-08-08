import { useEffect, useState } from 'react'
import { Badge } from '../components/ui/Badge'
import type { BadgeVariant } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { ProgressBar } from '../components/ProgressBar'
import { fetchCourses, fetchEnrollments } from '../lib/coursesApi'
import type { CourseListItem, Enrollment } from '../types/courses'

const STATUS_LABEL: Record<string, string> = {
  NOT_STARTED: 'Not started',
  IN_PROGRESS: 'In progress',
  COMPLETED: 'Completed',
}

const STATUS_BADGE: Record<string, BadgeVariant> = {
  NOT_STARTED: 'neutral',
  IN_PROGRESS: 'navy',
  COMPLETED: 'gold',
}

// A learner's own progress report — the personal counterpart to the admin
// cross-learner ReportsPage. Reuses the same enrollment data the Dashboard
// and course player already rely on, scoped to the caller's own rows.
export function LearnerReportsPage() {
  const [enrollments, setEnrollments] = useState<Enrollment[] | null>(null)
  const [courses, setCourses] = useState<CourseListItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([fetchEnrollments(), fetchCourses()])
      .then(([enrollmentList, courseList]) => {
        setEnrollments(enrollmentList)
        setCourses(courseList)
      })
      .catch(() => setError('Could not load your report.'))
  }, [])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!enrollments) return <p className="text-sm text-neutral-500">Loading…</p>

  const courseById = new Map(courses.map((course) => [course.id, course]))

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">My Reports</h1>
      <p className="mt-1 text-sm text-neutral-500">Your progress across every course you're enrolled in.</p>

      <Card className="mt-6 overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-3">Course</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Progress</th>
              <th className="px-4 py-3">Enrolled</th>
              <th className="px-4 py-3">Completed</th>
            </tr>
          </thead>
          <tbody>
            {enrollments.map((enrollment) => {
              const course = courseById.get(enrollment.course)
              return (
                <tr key={enrollment.id} className="border-b border-neutral-100 last:border-0">
                  <td className="px-4 py-3 font-medium text-neutral-900">{course?.title ?? `Course #${enrollment.course}`}</td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_BADGE[enrollment.status] ?? 'neutral'}>
                      {STATUS_LABEL[enrollment.status] ?? enrollment.status}
                    </Badge>
                  </td>
                  <td className="w-40 px-4 py-3">
                    <ProgressBar percent={enrollment.progress_percent} />
                  </td>
                  <td className="px-4 py-3 text-neutral-500">{new Date(enrollment.enrolled_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-neutral-500">
                    {enrollment.completed_at ? new Date(enrollment.completed_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              )
            })}
            {enrollments.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-neutral-400">
                  You're not enrolled in any courses yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
