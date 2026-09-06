import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { deleteCourse, fetchCourses } from '../../lib/coursesApi'
import type { CourseListItem } from '../../types/courses'

export function AdminCourseListPage() {
  const [courses, setCourses] = useState<CourseListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deletingSlug, setDeletingSlug] = useState<string | null>(null)

  function loadCourses() {
    fetchCourses()
      .then(setCourses)
      .catch(() => setError('Could not load courses.'))
  }

  useEffect(loadCourses, [])

  async function handleDelete(course: CourseListItem) {
    if (!window.confirm(`Delete "${course.title}"? This removes all its modules, lessons, and pages. This cannot be undone.`)) {
      return
    }
    setDeletingSlug(course.slug)
    setError(null)
    try {
      await deleteCourse(course.slug)
      loadCourses()
    } catch {
      setError('Could not delete this course.')
    } finally {
      setDeletingSlug(null)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-neutral-900">Courses</h1>
        <Link
          to="/admin/courses/new"
          className="rounded-md bg-brand-navy px-3 py-2 text-sm font-medium text-white transition hover:bg-brand-navy-light"
        >
          New Course
        </Link>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {courses && (
        <Card className="mt-4 overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Organization</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {courses.map((course) => (
                <tr key={course.id} className="border-b border-neutral-100 last:border-0">
                  <td className="px-4 py-3 font-medium text-neutral-900">
                    {course.title}
                    {course.cloned_from_title && (
                      <span className="ml-2 rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-500">
                        cloned from {course.cloned_from_title}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-neutral-500">{course.content_owner}</td>
                  <td className="px-4 py-3 text-neutral-500">{course.organization_name ?? '—'}</td>
                  <td className="px-4 py-3">
                    <Badge variant={course.is_published ? 'navy' : 'gold'}>
                      {course.is_published ? 'Published' : 'Draft'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <Link to={`/admin/courses/${course.slug}`} className="text-brand-navy underline">
                        Manage
                      </Link>
                      <button
                        type="button"
                        disabled={deletingSlug === course.slug}
                        onClick={() => void handleDelete(course)}
                        className="text-red-600 underline disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {deletingSlug === course.slug ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {courses.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-neutral-400">
                    No courses yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
