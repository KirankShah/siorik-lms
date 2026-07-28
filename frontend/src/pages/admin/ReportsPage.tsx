import { useEffect, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { downloadEnrollmentReportCsv, fetchCourses, fetchEnrollmentReport } from '../../lib/coursesApi'
import type { ReportRow } from '../../types/admin'
import type { CourseListItem } from '../../types/courses'

const STATUS_OPTIONS = ['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED']

export function ReportsPage() {
  const [courses, setCourses] = useState<CourseListItem[]>([])
  const [rows, setRows] = useState<ReportRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isExporting, setIsExporting] = useState(false)

  const [courseId, setCourseId] = useState('')
  const [status, setStatus] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  useEffect(() => {
    fetchCourses().then(setCourses).catch(() => {})
  }, [])

  function loadReport() {
    setError(null)
    fetchEnrollmentReport({
      course: courseId ? Number(courseId) : undefined,
      status: status || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })
      .then(setRows)
      .catch(() => setError('Could not load the report.'))
  }

  useEffect(loadReport, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleExport() {
    setIsExporting(true)
    try {
      await downloadEnrollmentReportCsv({
        course: courseId ? Number(courseId) : undefined,
        status: status || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      })
    } catch {
      setError('Could not export the report.')
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-neutral-900">Learner Report</h1>
        <Button size="sm" disabled={isExporting} onClick={handleExport}>
          {isExporting ? 'Exporting…' : 'Export CSV'}
        </Button>
      </div>

      <Card className="mt-4 flex flex-wrap items-end gap-3 p-4">
        <div>
          <label className="block text-xs font-medium text-neutral-500">Course</label>
          <select
            value={courseId}
            onChange={(e) => setCourseId(e.target.value)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          >
            <option value="">All courses</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500">Completed from</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500">Completed to</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          />
        </div>
        <Button variant="outline" size="sm" onClick={loadReport}>
          Apply filters
        </Button>
      </Card>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {rows && (
        <Card className="mt-4 overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-3">Learner</th>
                <th className="px-4 py-3">Course</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Completed</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-b border-neutral-100 last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-neutral-900">{row.learner_name}</div>
                    <div className="text-xs text-neutral-400">{row.learner_email}</div>
                  </td>
                  <td className="px-4 py-3">{row.course_title}</td>
                  <td className="px-4 py-3">{row.status}</td>
                  <td className="px-4 py-3">{row.score_percent !== null ? `${row.score_percent}%` : '—'}</td>
                  <td className="px-4 py-3">
                    {row.completion_date ? new Date(row.completion_date).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-neutral-400">
                    No matching enrollments.
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
