import { useEffect, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useAuth } from '../../context/AuthContext'
import {
  downloadPeriodicExamReportCsv,
  downloadPeriodicExamReportXlsx,
  fetchPeriodicExamReport,
  fetchPeriodicExamReportCycles,
  fetchPlatformPeriodicExamOrganizations,
} from '../../lib/periodicExamsApi'
import type {
  PeriodicExamReportCycle,
  PeriodicExamReportPage,
  PeriodicExamReportStatus,
  PlatformPeriodicExamOrganization,
} from '../../types/periodicExams'

export function PeriodicExamReportPage() {
  const { user } = useAuth()
  const platform = user?.role === 'PLATFORM_ADMIN'
  const [organizations, setOrganizations] = useState<PlatformPeriodicExamOrganization[]>([])
  const [organizationId, setOrganizationId] = useState<number | undefined>()
  const [cycles, setCycles] = useState<PeriodicExamReportCycle[]>([])
  const [cycleId, setCycleId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<PeriodicExamReportStatus | ''>('')
  const [page, setPage] = useState(1)
  const [report, setReport] = useState<PeriodicExamReportPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!platform) return
    fetchPlatformPeriodicExamOrganizations()
      .then((items) => {
        const enabled = items.filter((item) => item.periodic_exam_enabled)
        setOrganizations(enabled)
        setOrganizationId(enabled[0]?.id)
        if (!enabled.length) setLoading(false)
      })
      .catch(() => {
        setError('Organizations could not be loaded.')
        setLoading(false)
      })
  }, [platform])

  useEffect(() => {
    if (platform && !organizationId) return
    setLoading(true)
    setError(null)
    fetchPeriodicExamReportCycles(organizationId)
      .then((items) => {
        setCycles(items)
        setCycleId(items[0]?.id ?? null)
        if (!items.length) {
          setReport(null)
          setLoading(false)
        }
      })
      .catch(() => {
        setError('Periodic Exam cycles could not be loaded.')
        setLoading(false)
      })
  }, [organizationId, platform])

  useEffect(() => {
    if (!cycleId) return
    setLoading(true)
    setError(null)
    fetchPeriodicExamReport(cycleId, { organizationId, search, status, page })
      .then(setReport)
      .catch(() => setError('The Periodic Exam report could not be loaded.'))
      .finally(() => setLoading(false))
  }, [cycleId, organizationId, page, search, status])

  function changeOrganization(value: number) {
    setOrganizationId(value)
    setCycleId(null)
    setPage(1)
    setReport(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Periodic Exam Report</h1>
        <p className="mt-1 text-sm text-neutral-500">Frozen learner and result snapshots by exam cycle.</p>
      </div>

      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          {platform && (
            <label className="text-sm font-medium text-neutral-700">Organization
              <select aria-label="Organization" value={organizationId ?? ''} onChange={(event) => changeOrganization(Number(event.target.value))} className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2">
                {organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
          )}
          <label className="text-sm font-medium text-neutral-700">Cycle
            <select aria-label="Cycle" value={cycleId ?? ''} onChange={(event) => { setCycleId(Number(event.target.value)); setPage(1) }} className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2">
              {cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.display_label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-neutral-700">Search
            <input aria-label="Search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Name, email, level or branch" className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2" />
          </label>
          <label className="text-sm font-medium text-neutral-700">Status
            <select aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value as PeriodicExamReportStatus | ''); setPage(1) }} className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2">
              <option value="">All statuses</option>
              {['Passed', 'Failed', 'Not attempted', 'In progress'].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        </div>
        <div className="mt-4 flex gap-2">
          <Button variant="outline" disabled={!cycleId} onClick={() => cycleId && void downloadPeriodicExamReportCsv(cycleId, organizationId)}>Download CSV</Button>
          <Button variant="outline" disabled={!cycleId} onClick={() => cycleId && void downloadPeriodicExamReportXlsx(cycleId, organizationId)}>Download Excel</Button>
        </div>
      </Card>

      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {loading ? (
        <p className="text-sm text-neutral-500">Loading report…</p>
      ) : !cycleId ? (
        <Card><p className="text-sm text-neutral-500">No Periodic Exam cycles are available.</p></Card>
      ) : report?.results.length === 0 ? (
        <Card><p className="text-sm text-neutral-500">No learners match this report.</p></Card>
      ) : report ? (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-neutral-200 text-sm">
            <thead className="bg-neutral-50"><tr>{['Staff name', 'Email', 'Level', 'Branch/department', 'Cycle', 'Attempted', 'Completed', 'Attempts used', 'Best score', 'Status', 'Last attempt date'].map((header) => <th key={header} className="px-3 py-3 text-left font-medium text-neutral-600">{header}</th>)}</tr></thead>
            <tbody className="divide-y divide-neutral-100">
              {report.results.map((row) => (
                <tr key={`${row.email}-${row.cycle}`}>
                  <td className="px-3 py-3">{row.staff_name}</td><td className="px-3 py-3">{row.email}</td><td className="px-3 py-3">{row.level}</td><td className="px-3 py-3">{row.branch_department || '—'}</td><td className="px-3 py-3">{row.cycle}</td><td className="px-3 py-3">{row.attempted ? 'Yes' : 'No'}</td><td className="px-3 py-3">{row.completed ? 'Yes' : 'No'}</td><td className="px-3 py-3">{row.attempts_used}</td><td className="px-3 py-3">{row.best_score == null ? '—' : `${row.best_score}%`}</td><td className="px-3 py-3">{row.status}</td><td className="px-3 py-3">{row.last_attempt_date ? new Date(row.last_attempt_date).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-neutral-200 p-4 text-sm">
            <span>{report.count} learners</span>
            <div className="flex gap-2"><Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button size="sm" variant="secondary" disabled={page * report.page_size >= report.count} onClick={() => setPage((value) => value + 1)}>Next</Button></div>
          </div>
        </Card>
      ) : null}
    </div>
  )
}
