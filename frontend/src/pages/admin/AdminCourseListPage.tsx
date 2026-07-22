import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
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
        <h1 className="text-lg font-semibold text-slate-900">Courses</h1>
        <Link
          to="/admin/courses/new"
          className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        >
          New Course
        </Link>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {courses && (
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {courses.map((course) => (
                <tr key={course.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3 font-medium text-slate-900">{course.title}</td>
                  <td className="px-4 py-3 text-slate-500">{course.content_owner}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        course.is_published ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {course.is_published ? 'Published' : 'Draft'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <Link to={`/admin/courses/${course.slug}/edit`} className="text-slate-900 underline">
                        Edit
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
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                    No courses yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
