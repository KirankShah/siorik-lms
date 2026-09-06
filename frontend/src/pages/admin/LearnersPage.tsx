import { useEffect, useState } from 'react'
import { Badge } from '../../components/ui/Badge'
import type { BadgeVariant } from '../../components/ui/Badge'
import { useAuth } from '../../context/AuthContext'
import { deleteLearner } from '../../lib/accountsApi'
import { ApiError } from '../../lib/apiClient'
import { fetchLearnerRoster } from '../../lib/coursesApi'
import { isPlatformAdminRole } from '../../lib/roles'
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
  const { user } = useAuth()
  const canDelete = isPlatformAdminRole(user?.role)
  const [rows, setRows] = useState<ReportRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null)

  function loadRows() {
    fetchLearnerRoster()
      .then(setRows)
      .catch(() => setError('Could not load learners.'))
  }

  useEffect(loadRows, [])

  async function handleDelete(row: ReportRow) {
    if (
      !window.confirm(
        `Delete ${row.learner_name} (${row.learner_email})? This permanently deletes their account and all their enrollments/progress. This cannot be undone.`
      )
    ) {
      return
    }
    setDeletingUserId(row.user_id)
    setError(null)
    try {
      await deleteLearner(row.user_id)
      loadRows()
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError('This account no longer exists.')
      } else {
        setError('Could not delete this learner.')
      }
    } finally {
      setDeletingUserId(null)
    }
  }

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
                {canDelete && <th className="px-4 py-3" />}
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
                  {canDelete && (
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        disabled={deletingUserId === row.user_id}
                        onClick={() => void handleDelete(row)}
                        className="text-red-600 underline disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {deletingUserId === row.user_id ? 'Deleting…' : 'Delete'}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={canDelete ? 5 : 4} className="px-4 py-6 text-center text-neutral-400">
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
