import { useEffect, useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import type { BadgeVariant } from '../../components/ui/Badge'
import { fetchLearnerRoster } from '../../lib/coursesApi'
import type { ReportRow } from '../../types/admin'

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

// One row per learner+course enrollment (a learner in 3 courses appears 3
// times) — same row shape as ReportsPage's filterable view, but served by a
// separate ORG_ADMIN/PLATFORM_ADMIN-only endpoint (see fetchLearnerRoster),
// since this page is restricted to org admins while Reports also allows
// INSTRUCTOR.
export function LearnersPage() {
  const [rows, setRows] = useState<ReportRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchLearnerRoster()
      .then(setRows)
      .catch(() => setError('Could not load learners.'))
  }, [])

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Learners</h1>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {rows && (
        <div className="mt-4 overflow-x-auto rounded-xl border border-neutral-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-3">Learner</th>
                <th className="px-4 py-3">Course</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-b border-neutral-100 last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-neutral-900">{row.learner_name}</div>
                    <div className="text-xs text-neutral-500">{row.learner_email}</div>
                  </td>
                  <td className="px-4 py-3 text-neutral-700">{row.course_title}</td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_BADGE[row.status] ?? 'neutral'}>{STATUS_LABEL[row.status] ?? row.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-neutral-700">
                    {row.score_percent !== null ? `${row.score_percent}%` : '—'}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-neutral-400">
                    No learners yet.
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
