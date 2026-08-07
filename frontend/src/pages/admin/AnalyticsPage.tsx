import { Fragment, useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizations } from '../../lib/accountsApi'
import { downloadAdminAnalyticsXlsx, fetchAdminAnalytics, fetchCourses } from '../../lib/coursesApi'
import type { AnalyticsOrganizationGroup, AnalyticsPassStatus, AnalyticsRow } from '../../types/admin'
import type { Organization } from '../../types/auth'
import type { CourseListItem } from '../../types/courses'

const PASS_STATUS_CLASSES: Record<AnalyticsPassStatus, string> = {
  PASSED: 'bg-emerald-50 text-emerald-800',
  FAILED: 'bg-red-50 text-red-800',
  IN_PROGRESS: 'bg-brand-navy/10 text-brand-navy',
  NOT_STARTED: 'bg-neutral-100 text-neutral-600',
}

const PASS_STATUS_LABEL: Record<AnalyticsPassStatus, string> = {
  PASSED: 'Passed',
  FAILED: 'Failed',
  IN_PROGRESS: 'In progress',
  NOT_STARTED: 'Not started',
}

function formatTimeSpent(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
}

function rowKey(row: AnalyticsRow): string {
  return `${row.user_id}-${row.course_id}`
}

export function AnalyticsPage() {
  const { user } = useAuth()
  const isPlatformAdmin = user?.role === 'PLATFORM_ADMIN'

  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [courses, setCourses] = useState<CourseListItem[]>([])
  const [groups, setGroups] = useState<AnalyticsOrganizationGroup[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isExporting, setIsExporting] = useState(false)
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const [organizationId, setOrganizationId] = useState('')
  const [courseId, setCourseId] = useState('')

  useEffect(() => {
    if (isPlatformAdmin) fetchOrganizations().then(setOrganizations).catch(() => {})
    fetchCourses().then(setCourses).catch(() => {})
  }, [isPlatformAdmin])

  function loadAnalytics() {
    setError(null)
    fetchAdminAnalytics({
      organization: organizationId ? Number(organizationId) : undefined,
      course: courseId ? Number(courseId) : undefined,
    })
      .then(setGroups)
      .catch(() => setError('Could not load the analytics dashboard.'))
  }

  useEffect(loadAnalytics, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleExport() {
    setIsExporting(true)
    try {
      await downloadAdminAnalyticsXlsx({
        organization: organizationId ? Number(organizationId) : undefined,
        course: courseId ? Number(courseId) : undefined,
      })
    } catch {
      setError('Could not export the analytics dashboard.')
    } finally {
      setIsExporting(false)
    }
  }

  function toggleRow(key: string) {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const totalRows = groups?.reduce((sum, group) => sum + group.rows.length, 0) ?? 0

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-neutral-900">Analytics</h1>
        <Button size="sm" disabled={isExporting} onClick={handleExport}>
          {isExporting ? 'Exporting…' : 'Export to Excel'}
        </Button>
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        Per-user course progress, pass/fail status, time spent, and quiz retake history, grouped by Organization.
      </p>

      <Card className="mt-4 flex flex-wrap items-end gap-3 p-4">
        {isPlatformAdmin && (
          <div>
            <label className="block text-xs font-medium text-neutral-500">Organization</label>
            <select
              value={organizationId}
              onChange={(e) => setOrganizationId(e.target.value)}
              className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
            >
              <option value="">All organizations</option>
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          </div>
        )}
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
        <Button variant="outline" size="sm" onClick={loadAnalytics}>
          Apply filters
        </Button>
      </Card>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {groups && totalRows === 0 && (
        <Card className="mt-4">
          <p className="text-center text-sm text-neutral-400">No matching enrollments.</p>
        </Card>
      )}

      {groups?.map((group) => (
        <Card key={group.organization_id ?? 'none'} className="mt-4 overflow-x-auto p-0">
          {group.rows.length > 0 && (
            <>
              <div className="border-b border-neutral-200 bg-neutral-50 px-4 py-3">
                <h2 className="text-sm font-semibold text-neutral-900">{group.organization_name}</h2>
                <p className="text-xs text-neutral-500">
                  {group.rows.length} enrollment{group.rows.length === 1 ? '' : 's'}
                </p>
              </div>
              <table className="w-full text-left text-sm">
                <thead className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-4 py-3" />
                    <th className="px-4 py-3">User</th>
                    <th className="px-4 py-3">Course</th>
                    <th className="px-4 py-3">% Completion</th>
                    <th className="px-4 py-3">Pass/Fail</th>
                    <th className="px-4 py-3">Final Score</th>
                    <th className="px-4 py-3">Time Spent</th>
                    <th className="px-4 py-3">Attempts</th>
                  </tr>
                </thead>
                <tbody>
                  {group.rows.map((row) => {
                    const key = rowKey(row)
                    const isExpanded = expandedRows.has(key)
                    return (
                      <Fragment key={key}>
                        <tr className="border-b border-neutral-100 last:border-0">
                          <td className="px-4 py-3">
                            {row.quizzes.length > 0 && (
                              <button
                                type="button"
                                onClick={() => toggleRow(key)}
                                aria-label={isExpanded ? 'Collapse quiz attempts' : 'Expand quiz attempts'}
                                className="text-neutral-400 hover:text-neutral-700"
                              >
                                {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                              </button>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-medium text-neutral-900">{row.user_name}</div>
                            <div className="text-xs text-neutral-400">{row.user_email}</div>
                          </td>
                          <td className="px-4 py-3">{row.course_title}</td>
                          <td className="px-4 py-3">{row.progress_percent}%</td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${PASS_STATUS_CLASSES[row.pass_status]}`}
                            >
                              {PASS_STATUS_LABEL[row.pass_status]}
                            </span>
                          </td>
                          <td className="px-4 py-3">{row.final_score !== null ? `${row.final_score}%` : '—'}</td>
                          <td className="px-4 py-3">{formatTimeSpent(row.time_spent_seconds)}</td>
                          <td className="px-4 py-3">{row.total_quiz_attempts}</td>
                        </tr>
                        {isExpanded && (
                          <tr className="border-b border-neutral-100 bg-neutral-50 last:border-0">
                            <td />
                            <td colSpan={7} className="px-4 py-3">
                              <div className="space-y-2">
                                {row.quizzes.map((quiz) => (
                                  <div key={quiz.quiz_id} className="text-xs">
                                    <span className="font-medium text-neutral-700">{quiz.quiz_title}:</span>{' '}
                                    {quiz.attempts.length === 0 ? (
                                      <span className="text-neutral-400">no attempts</span>
                                    ) : (
                                      quiz.attempts.map((attempt, index) => (
                                        <span key={attempt.attempt_number} className="text-neutral-600">
                                          {index > 0 && ', '}
                                          attempt {attempt.attempt_number}: {attempt.score_percent}%{' '}
                                          <span className={attempt.passed ? 'text-emerald-600' : 'text-red-600'}>
                                            ({attempt.passed ? 'passed' : 'failed'})
                                          </span>
                                        </span>
                                      ))
                                    )}
                                  </div>
                                ))}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </>
          )}
        </Card>
      ))}
    </div>
  )
}
