import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/apiClient'
import { bulkCreateDemoUsers, createDemoUser, fetchOrganizations } from '../../lib/accountsApi'
import type { DemoUserBulkResult } from '../../lib/accountsApi'
import type { Organization } from '../../types/auth'

export function DemoUsersPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([])

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [organizationId, setOrganizationId] = useState('')
  const [singleError, setSingleError] = useState<string | null>(null)
  const [singleSuccess, setSingleSuccess] = useState<string | null>(null)
  const [isSubmittingSingle, setIsSubmittingSingle] = useState(false)

  const [file, setFile] = useState<File | null>(null)
  const [bulkResult, setBulkResult] = useState<DemoUserBulkResult | null>(null)
  const [bulkError, setBulkError] = useState<string | null>(null)
  const [isSubmittingBulk, setIsSubmittingBulk] = useState(false)

  useEffect(() => {
    fetchOrganizations().then(setOrganizations).catch(() => {})
  }, [])

  async function handleSingleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!organizationId) return
    setSingleError(null)
    setSingleSuccess(null)
    setIsSubmittingSingle(true)
    try {
      const user = await createDemoUser({ name, email, organization: Number(organizationId) })
      setSingleSuccess(`Invite sent to ${user.email}.`)
      setName('')
      setEmail('')
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string; email?: string[] } | null
        setSingleError(body?.detail ?? body?.email?.[0] ?? 'Could not create this user.')
      } else {
        setSingleError('Could not create this user.')
      }
    } finally {
      setIsSubmittingSingle(false)
    }
  }

  async function handleBulkSubmit() {
    if (!file) return
    setBulkError(null)
    setBulkResult(null)
    setIsSubmittingBulk(true)
    try {
      const result = await bulkCreateDemoUsers(file)
      setBulkResult(result)
    } catch {
      setBulkError('Could not process the CSV file.')
    } finally {
      setIsSubmittingBulk(false)
    }
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Demo Users</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Provisions a learner account with a temporary password and emails an invite. The account is forced through a
        password-reset flow on first login.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-semibold text-neutral-900">Add a single user</h2>
          <form onSubmit={handleSingleSubmit} className="mt-4 space-y-4">
            <Input id="demo-name" label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
            <Input
              id="demo-email"
              label="Email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <div>
              <label htmlFor="demo-org" className="block text-sm font-medium text-neutral-700">
                Organization
              </label>
              <select
                id="demo-org"
                required
                value={organizationId}
                onChange={(e) => setOrganizationId(e.target.value)}
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm"
              >
                <option value="">Select an organization…</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </div>

            {singleError && <p className="text-sm text-red-600">{singleError}</p>}
            {singleSuccess && <p className="text-sm text-emerald-700">{singleSuccess}</p>}

            <Button type="submit" disabled={isSubmittingSingle || !organizationId}>
              {isSubmittingSingle ? 'Creating…' : 'Create and send invite'}
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold text-neutral-900">Bulk upload via CSV</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Columns: <code className="rounded bg-neutral-100 px-1 py-0.5">name, email, organization</code> (organization
            matched by name). A header row is optional.
          </p>

          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700">CSV file</label>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="mt-1 text-sm"
              />
            </div>

            {bulkError && <p className="text-sm text-red-600">{bulkError}</p>}

            <Button disabled={!file || isSubmittingBulk} onClick={() => void handleBulkSubmit()}>
              {isSubmittingBulk ? 'Uploading…' : 'Upload and provision'}
            </Button>
          </div>

          {bulkResult && (
            <div className="mt-4 space-y-3 border-t border-neutral-100 pt-4">
              <p className="text-sm text-emerald-700">
                Created {bulkResult.created.length} account{bulkResult.created.length === 1 ? '' : 's'}
                {bulkResult.created.length > 0 && `: ${bulkResult.created.join(', ')}`}
              </p>

              {bulkResult.failed.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-red-700">
                    {bulkResult.failed.length} row{bulkResult.failed.length === 1 ? '' : 's'} failed:
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
                        {bulkResult.failed.map((failure) => (
                          <tr key={`${failure.row}-${failure.email}`} className="border-t border-neutral-100">
                            <td className="py-1 pr-3 text-neutral-500">{failure.row}</td>
                            <td className="py-1 pr-3 text-neutral-900">{failure.email || '—'}</td>
                            <td className="py-1 text-neutral-600">{failure.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
