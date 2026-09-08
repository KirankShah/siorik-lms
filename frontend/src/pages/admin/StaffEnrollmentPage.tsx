import { useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { bulkEnrollStaff } from '../../lib/accountsApi'
import type { StaffEnrollResult } from '../../lib/accountsApi'
import { ApiError } from '../../lib/apiClient'

const TEMPLATE_COLUMNS = [
  'Full Name',
  'Email Address',
  'Corporate Title',
  'Functional Title',
  'Branch / Department',
  'Assessment Level',
  'Phone Number',
  'Organization',
]

const LEVEL_NAMES = ['Front-Line Level', 'Officer Level', 'Middle Management Level', 'Top Management Level']

export function StaffEnrollmentPage() {
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<StaffEnrollResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit() {
    if (!file) return
    setIsSubmitting(true)
    setError(null)
    setResult(null)
    try {
      setResult(await bulkEnrollStaff(file))
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string } | null
        setError(body?.detail ?? 'The file could not be read.')
      } else {
        setError('Could not process the file. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Staff Enrollment</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Upload the staff enrollment spreadsheet (<code className="rounded bg-neutral-100 px-1 py-0.5">.xlsx</code> or{' '}
        <code className="rounded bg-neutral-100 px-1 py-0.5">.csv</code>) to create a login account for each staff
        member. Each person gets an email with a temporary password and is placed at the assessment level named in
        their row — their role-based assessment then appears automatically on their dashboard. Rows that fail
        validation are reported below; the rest still go through.
      </p>

      <Card className="mt-4 space-y-4">
        <div>
          <label htmlFor="staff-file" className="block text-sm font-medium text-neutral-700">
            Spreadsheet
          </label>
          <input
            id="staff-file"
            type="file"
            accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 text-sm"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button disabled={!file || isSubmitting} onClick={handleSubmit}>
          {isSubmitting ? 'Enrolling…' : 'Enroll Staff'}
        </Button>
      </Card>

      <Card className="mt-4">
        <h2 className="text-sm font-semibold text-neutral-900">Expected columns</h2>
        <p className="mt-1 text-sm text-neutral-500">
          A leading title row is fine — the header is detected automatically. Column order doesn't matter; matching is
          case-insensitive.
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {TEMPLATE_COLUMNS.map((column) => (
            <code key={column} className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700">
              {column}
            </code>
          ))}
        </div>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-neutral-500">
          <li>
            <span className="font-medium text-neutral-700">Full Name</span>, <span className="font-medium text-neutral-700">Email Address</span>,{' '}
            <span className="font-medium text-neutral-700">Assessment Level</span> and{' '}
            <span className="font-medium text-neutral-700">Organization</span> are required; the rest are optional.
          </li>
          <li>
            <span className="font-medium text-neutral-700">Assessment Level</span> must be one of:{' '}
            {LEVEL_NAMES.map((name, i) => (
              <span key={name}>
                <code className="rounded bg-neutral-100 px-1 py-0.5 text-xs">{name}</code>
                {i < LEVEL_NAMES.length - 1 ? ', ' : ''}
              </span>
            ))}
            . The older labels (Assistant-Supervisor, Officer, Management, Senior Management) are also accepted.
          </li>
          <li>
            As an organization admin you can only enrol staff into your own organization — a row naming a different one
            is rejected.
          </li>
        </ul>
      </Card>

      {result && (
        <Card className="mt-4 space-y-3">
          <p className="text-sm text-emerald-700">
            Enrolled {result.created.length} staff member{result.created.length === 1 ? '' : 's'}.
          </p>

          {result.created.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-neutral-500 uppercase">
                  <tr>
                    <th className="py-1 pr-3">Email</th>
                    <th className="py-1">Assessment level</th>
                  </tr>
                </thead>
                <tbody>
                  {result.created.map((entry) => (
                    <tr key={entry.email} className="border-t border-neutral-100">
                      <td className="py-1 pr-3 text-neutral-900">{entry.email}</td>
                      <td className="py-1 text-neutral-600">{entry.assessment_level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.failed.length > 0 && (
            <div>
              <p className="text-sm font-medium text-red-700">
                {result.failed.length} row{result.failed.length === 1 ? '' : 's'} not enrolled:
              </p>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-neutral-500 uppercase">
                    <tr>
                      <th className="py-1 pr-3">Row</th>
                      <th className="py-1 pr-3">Email</th>
                      <th className="py-1">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.failed.map((failure, index) => (
                      <tr key={`${failure.email}-${index}`} className="border-t border-neutral-100">
                        <td className="py-1 pr-3 text-neutral-500">{failure.row ?? '—'}</td>
                        <td className="py-1 pr-3 text-neutral-900">{failure.email || '—'}</td>
                        <td className="py-1 text-neutral-600">{failure.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
