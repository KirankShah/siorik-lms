import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import type { BadgeVariant } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { fetchEnrollmentReport } from '../../lib/coursesApi'
import type { ReportRow } from '../../types/admin'
import type { CourseDashboardContext } from './CourseDashboardLayout'

const STATUS_BADGE: Record<string, BadgeVariant> = {
  COMPLETED: 'gold',
  IN_PROGRESS: 'navy',
  NOT_STARTED: 'neutral',
}

const STATUS_LABEL: Record<string, string> = {
  COMPLETED: 'Completed',
  IN_PROGRESS: 'In progress',
  NOT_STARTED: 'Not started',
}

export function CourseAnalyzeTab() {
  const { course } = useOutletContext<CourseDashboardContext>()
  const [rows, setRows] = useState<ReportRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchEnrollmentReport({ course: course.id })
      .then(setRows)
      .catch(() => setError('Could not load analytics.'))
  }, [course.id])

  const completionRate =
    rows && rows.length > 0 ? Math.round((rows.filter((row) => row.status === 'COMPLETED').length / rows.length) * 100) : 0

  const scored = rows ? rows.filter((row) => row.score_percent !== null) : []
  const averageScore =
    scored.length > 0
      ? Math.round(scored.reduce((sum, row) => sum + (row.score_percent ?? 0), 0) / scored.length)
      : null

  return (
    <div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <p className="text-2xl font-semibold text-neutral-900">{rows ? `${completionRate}%` : '—'}</p>
          <p className="text-xs text-neutral-500">Completion rate ({rows?.length ?? 0} enrolled)</p>
        </Card>
        <Card>
          <p className="text-2xl font-semibold text-neutral-900">{averageScore !== null ? `${averageScore}%` : '—'}</p>
          <p className="text-xs text-neutral-500">Average quiz score</p>
        </Card>
      </div>

      <Card className="mt-6 overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-3">Learner</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Completed</th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((row, index) => (
              <tr key={index} className="border-b border-neutral-100 last:border-0">
                <td className="px-4 py-3">
                  <div className="font-medium text-neutral-900">{row.learner_name}</div>
                  <div className="text-xs text-neutral-500">{row.learner_email}</div>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={STATUS_BADGE[row.status] ?? 'neutral'}>{STATUS_LABEL[row.status] ?? row.status}</Badge>
                </td>
                <td className="px-4 py-3 text-neutral-700">{row.score_percent !== null ? `${row.score_percent}%` : '—'}</td>
                <td className="px-4 py-3 text-neutral-700">
                  {row.completion_date ? new Date(row.completion_date).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
            {rows && rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-neutral-400">
                  No learners enrolled yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
