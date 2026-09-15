import { useEffect, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizations } from '../../lib/accountsApi'
import {
  downloadStaffTrainingReportCsv,
  downloadStaffTrainingReportXlsx,
  fetchStaffTrainingReport,
} from '../../lib/coursesApi'
import { ApiError } from '../../lib/apiClient'
import { isPlatformAdminRole } from '../../lib/roles'
import type { StaffTrainingReport } from '../../types/admin'
import type { Organization } from '../../types/auth'

function firstOfMonth(): string {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10)
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export function StaffTrainingReportPage() {
  const { user } = useAuth()
  const isPlatformAdmin = isPlatformAdminRole(user?.role)

  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [organizationId, setOrganizationId] = useState('')
  const [dateFrom, setDateFrom] = useState(firstOfMonth())
  const [dateTo, setDateTo] = useState(today())

  const [report, setReport] = useState<StaffTrainingReport | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isExporting, setIsExporting] = useState<'csv' | 'xlsx' | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isPlatformAdmin) fetchOrganizations().then(setOrganizations).catch(() => {})
  }, [isPlatformAdmin])

  function currentFilters() {
    return {
      date_from: dateFrom,
      date_to: dateTo,
      organization: isPlatformAdmin && organizationId ? Number(organizationId) : undefined,
    }
  }

  async function handleGenerate() {
    if (isPlatformAdmin && !organizationId) {
      setError('Select an organization first.')
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      setReport(await fetchStaffTrainingReport(currentFilters()))
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string } | null
        setError(body?.detail ?? 'Could not generate the report — check the date range.')
      } else {
        setError('Could not generate the report.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  async function handleExport(format: 'csv' | 'xlsx') {
    if (isPlatformAdmin && !organizationId) {
      setError('Select an organization first.')
      return
    }
    setIsExporting(format)
    setError(null)
    try {
      const download = format === 'csv' ? downloadStaffTrainingReportCsv : downloadStaffTrainingReportXlsx
      await download(currentFilters())
    } catch {
      setError(`Could not export the report as ${format.toUpperCase()}.`)
    } finally {
      setIsExporting(null)
    }
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Staff Training Report</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Per-staff Learning Path and Level Assessment results for a date range — course completions and assessment
        attempts are scoped to the range; staff details (name, titles) are always current.
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
              <option value="">Select an organization…</option>
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="block text-xs font-medium text-neutral-500">Start date</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500">End date</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          />
        </div>
        <Button variant="outline" size="sm" disabled={isLoading} onClick={handleGenerate}>
          {isLoading ? 'Generating…' : 'Generate report'}
        </Button>
        <div className="ml-auto flex gap-2">
          <Button size="sm" disabled={isExporting !== null} onClick={() => handleExport('csv')}>
            {isExporting === 'csv' ? 'Exporting…' : 'Export CSV'}
          </Button>
          <Button size="sm" disabled={isExporting !== null} onClick={() => handleExport('xlsx')}>
            {isExporting === 'xlsx' ? 'Exporting…' : 'Export Excel'}
          </Button>
        </div>
      </Card>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {report && (
        <Card className="mt-4 space-y-2 overflow-x-auto p-0">
          <div className="border-b border-neutral-200 bg-neutral-50 px-4 py-3">
            <p className="text-xs text-neutral-500">
              {report.rows.length} staff member{report.rows.length === 1 ? '' : 's'}
            </p>
          </div>
          <table className="w-full text-left text-xs">
            <thead className="border-b border-neutral-200 uppercase tracking-wide text-neutral-500">
              <tr>
                {report.headers.map((header) => (
                  <th key={header} className="px-3 py-2 whitespace-nowrap">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-b border-neutral-100 last:border-0">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 whitespace-nowrap text-neutral-700">
                      {cell === '' ? <span className="text-neutral-300">—</span> : cell}
                    </td>
                  ))}
                </tr>
              ))}
              {report.rows.length === 0 && (
                <tr>
                  <td colSpan={report.headers.length} className="px-3 py-6 text-center text-neutral-400">
                    No staff found for this organization.
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
