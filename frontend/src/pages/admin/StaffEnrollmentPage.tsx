import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { useAuth } from '../../context/AuthContext'
import {
  bulkEnrollStaff,
  createStaffMember,
  deactivateStaffMember,
  fetchOrganizations,
  fetchStaffList,
  reactivateStaffMember,
} from '../../lib/accountsApi'
import type { PaginatedResult, StaffEnrollResult } from '../../lib/accountsApi'
import { ApiError } from '../../lib/apiClient'
import { isPlatformAdminRole } from '../../lib/roles'
import type { AssessmentLevel, Organization, User } from '../../types/auth'

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

const ASSESSMENT_LEVELS: { value: AssessmentLevel; label: string }[] = [
  { value: 'assistant_supervisor', label: 'Front-Line Level' },
  { value: 'officer', label: 'Officer Level' },
  { value: 'management', label: 'Middle Management Level' },
  { value: 'senior_management', label: 'Top Management Level' },
]

const LEVEL_LABEL: Record<string, string> = Object.fromEntries(ASSESSMENT_LEVELS.map((l) => [l.value, l.label]))

const PAGE_SIZE = 25

const EMPTY_ADD_FORM = {
  name: '',
  email: '',
  corporate_title: '',
  functional_title: '',
  branch_department: '',
  assessment_level: '' as AssessmentLevel | '',
  phone_number: '',
  organization: '',
}

export function StaffEnrollmentPage() {
  const { user } = useAuth()
  const isPlatformAdmin = isPlatformAdminRole(user?.role)

  // --- Individual add form ---
  const [addForm, setAddForm] = useState(EMPTY_ADD_FORM)
  const [addError, setAddError] = useState<string | null>(null)
  const [addSuccess, setAddSuccess] = useState<string | null>(null)
  const [isAdding, setIsAdding] = useState(false)

  // --- Bulk upload ---
  const [file, setFile] = useState<File | null>(null)
  const [bulkResult, setBulkResult] = useState<StaffEnrollResult | null>(null)
  const [bulkError, setBulkError] = useState<string | null>(null)
  const [isBulkSubmitting, setIsBulkSubmitting] = useState(false)

  // --- Staff directory (search + pagination + deactivate/reactivate) ---
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'active' | 'inactive'>('active')
  const [orgFilter, setOrgFilter] = useState('')
  const [page, setPage] = useState(1)
  const [staffPage, setStaffPage] = useState<PaginatedResult<User> | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [busyStaffId, setBusyStaffId] = useState<number | null>(null)

  useEffect(() => {
    if (isPlatformAdmin) fetchOrganizations().then(setOrganizations).catch(() => {})
  }, [isPlatformAdmin])

  // Debounce the free-text search box so every keystroke doesn't fire a request.
  useEffect(() => {
    const timeout = setTimeout(() => {
      setPage(1)
      setSearch(searchInput.trim())
    }, 350)
    return () => clearTimeout(timeout)
  }, [searchInput])

  function loadStaff() {
    setListError(null)
    fetchStaffList({
      search: search || undefined,
      status: statusFilter,
      organization: isPlatformAdmin && orgFilter ? Number(orgFilter) : undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then(setStaffPage)
      .catch(() => setListError('Could not load the staff list.'))
  }

  useEffect(loadStaff, [search, statusFilter, orgFilter, page, isPlatformAdmin]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAddSubmit(event: FormEvent) {
    event.preventDefault()
    setAddError(null)
    setAddSuccess(null)
    setIsAdding(true)
    try {
      const created = await createStaffMember({
        name: addForm.name,
        email: addForm.email,
        assessment_level: addForm.assessment_level,
        corporate_title: addForm.corporate_title,
        functional_title: addForm.functional_title,
        branch_department: addForm.branch_department,
        phone_number: addForm.phone_number,
        ...(isPlatformAdmin && addForm.organization ? { organization: Number(addForm.organization) } : {}),
      })
      setAddSuccess(`Enrolled ${created.email}. A welcome email with a temporary password has been sent.`)
      setAddForm(EMPTY_ADD_FORM)
      setPage(1)
      loadStaff()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string; assessment_level?: string[]; organization?: string[] } | null
        setAddError(
          body?.detail ?? body?.assessment_level?.[0] ?? body?.organization?.[0] ?? 'Could not add this staff member.'
        )
      } else {
        setAddError('Could not add this staff member.')
      }
    } finally {
      setIsAdding(false)
    }
  }

  async function handleBulkSubmit() {
    if (!file) return
    setIsBulkSubmitting(true)
    setBulkError(null)
    setBulkResult(null)
    try {
      setBulkResult(await bulkEnrollStaff(file))
      setPage(1)
      loadStaff()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string } | null
        setBulkError(body?.detail ?? 'The file could not be read.')
      } else {
        setBulkError('Could not process the file. Please try again.')
      }
    } finally {
      setIsBulkSubmitting(false)
    }
  }

  async function handleDeactivate(staff: User) {
    const name = `${staff.first_name} ${staff.last_name}`.trim() || staff.email
    if (
      !window.confirm(
        `This will revoke ${name}'s access immediately. Their training history and certificates will be preserved. Continue?`
      )
    ) {
      return
    }
    setBusyStaffId(staff.id)
    setListError(null)
    try {
      await deactivateStaffMember(staff.id)
      loadStaff()
    } catch {
      setListError('Could not deactivate this staff member.')
    } finally {
      setBusyStaffId(null)
    }
  }

  async function handleReactivate(staff: User) {
    setBusyStaffId(staff.id)
    setListError(null)
    try {
      await reactivateStaffMember(staff.id)
      loadStaff()
    } catch {
      setListError('Could not reactivate this staff member.')
    } finally {
      setBusyStaffId(null)
    }
  }

  const staffRows = staffPage?.results ?? []

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Staff Enrollment</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Add staff one at a time or upload a spreadsheet. Each person gets an email with a temporary password and is
        placed at the assessment level selected — their role-based assessment then appears automatically on their
        dashboard.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-semibold text-neutral-900">Add a staff member</h2>
          <form onSubmit={handleAddSubmit} className="mt-4 space-y-4">
            <Input
              id="staff-name"
              label="Full Name"
              required
              value={addForm.name}
              onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
            />
            <Input
              id="staff-email"
              label="Email"
              type="email"
              required
              value={addForm.email}
              onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
            />
            {isPlatformAdmin && (
              <div>
                <label htmlFor="staff-org" className="block text-sm font-medium text-neutral-700">
                  Organization
                </label>
                <select
                  id="staff-org"
                  required
                  value={addForm.organization}
                  onChange={(e) => setAddForm((f) => ({ ...f, organization: e.target.value }))}
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
            )}
            <div className="grid grid-cols-2 gap-4">
              <Input
                id="staff-corporate-title"
                label="Corporate Title"
                value={addForm.corporate_title}
                onChange={(e) => setAddForm((f) => ({ ...f, corporate_title: e.target.value }))}
              />
              <Input
                id="staff-functional-title"
                label="Functional Title"
                value={addForm.functional_title}
                onChange={(e) => setAddForm((f) => ({ ...f, functional_title: e.target.value }))}
              />
            </div>
            <Input
              id="staff-branch"
              label="Branch/Department"
              value={addForm.branch_department}
              onChange={(e) => setAddForm((f) => ({ ...f, branch_department: e.target.value }))}
            />
            <div>
              <label htmlFor="staff-level" className="block text-sm font-medium text-neutral-700">
                Assessment Level
              </label>
              <select
                id="staff-level"
                required
                value={addForm.assessment_level}
                onChange={(e) => setAddForm((f) => ({ ...f, assessment_level: e.target.value as AssessmentLevel }))}
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm"
              >
                <option value="">Select a level…</option>
                {ASSESSMENT_LEVELS.map((level) => (
                  <option key={level.value} value={level.value}>
                    {level.label}
                  </option>
                ))}
              </select>
            </div>
            <Input
              id="staff-phone"
              label="Phone Number (optional)"
              value={addForm.phone_number}
              onChange={(e) => setAddForm((f) => ({ ...f, phone_number: e.target.value }))}
            />

            {addError && <p className="text-sm text-red-600">{addError}</p>}
            {addSuccess && <p className="text-sm text-emerald-700">{addSuccess}</p>}

            <Button
              type="submit"
              disabled={
                isAdding ||
                !addForm.name ||
                !addForm.email ||
                !addForm.assessment_level ||
                (isPlatformAdmin && !addForm.organization)
              }
            >
              {isAdding ? 'Enrolling…' : 'Add staff member'}
            </Button>
          </form>
        </Card>

        <div className="space-y-6">
          <Card className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold text-neutral-900">Bulk upload</h2>
              <p className="mt-1 text-sm text-neutral-500">
                Upload the staff enrollment spreadsheet (<code className="rounded bg-neutral-100 px-1 py-0.5">.xlsx</code>{' '}
                or <code className="rounded bg-neutral-100 px-1 py-0.5">.csv</code>). Rows that fail validation are
                reported below; the rest still go through.
              </p>
            </div>

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

            {bulkError && <p className="text-sm text-red-600">{bulkError}</p>}

            <Button disabled={!file || isBulkSubmitting} onClick={handleBulkSubmit}>
              {isBulkSubmitting ? 'Enrolling…' : 'Enroll Staff'}
            </Button>

            <div className="border-t border-neutral-100 pt-3">
              <p className="text-xs font-medium text-neutral-700">Expected columns</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {TEMPLATE_COLUMNS.map((column) => (
                  <code key={column} className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-700">
                    {column}
                  </code>
                ))}
              </div>
            </div>
          </Card>

          {bulkResult && (
            <Card className="space-y-3">
              <p className="text-sm text-emerald-700">
                Enrolled {bulkResult.created.length} staff member{bulkResult.created.length === 1 ? '' : 's'}.
              </p>

              {bulkResult.failed.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-red-700">
                    {bulkResult.failed.length} row{bulkResult.failed.length === 1 ? '' : 's'} not enrolled:
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
                        {bulkResult.failed.map((failure, index) => (
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
      </div>

      <Card className="mt-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-sm font-semibold text-neutral-900">Staff directory</h2>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs font-medium text-neutral-500">Search</label>
              <input
                type="text"
                placeholder="Name or email…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
              />
            </div>
            {isPlatformAdmin && (
              <div>
                <label className="block text-xs font-medium text-neutral-500">Organization</label>
                <select
                  value={orgFilter}
                  onChange={(e) => {
                    setPage(1)
                    setOrgFilter(e.target.value)
                  }}
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
            <div className="flex overflow-hidden rounded-md border border-neutral-300">
              {(['active', 'inactive'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    setPage(1)
                    setStatusFilter(option)
                  }}
                  className={`px-3 py-1.5 text-sm capitalize transition ${
                    statusFilter === option ? 'bg-brand-navy text-white' : 'bg-white text-neutral-600 hover:bg-neutral-50'
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        </div>

        {listError && <p className="mt-4 text-sm text-red-600">{listError}</p>}

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-200 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">Corporate Title</th>
                <th className="py-2 pr-3">Functional Title</th>
                <th className="py-2 pr-3">Branch/Department</th>
                <th className="py-2 pr-3">Assessment Level</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {staffRows.map((staff) => (
                <tr key={staff.id} className="border-b border-neutral-100 last:border-0">
                  <td className="py-2 pr-3 text-neutral-900">{`${staff.first_name} ${staff.last_name}`.trim() || '—'}</td>
                  <td className="py-2 pr-3 text-neutral-700">{staff.email}</td>
                  <td className="py-2 pr-3 text-neutral-700">{staff.corporate_title || '—'}</td>
                  <td className="py-2 pr-3 text-neutral-700">{staff.functional_title || '—'}</td>
                  <td className="py-2 pr-3 text-neutral-700">{staff.branch_department || '—'}</td>
                  <td className="py-2 pr-3 text-neutral-700">
                    {staff.assessment_level ? LEVEL_LABEL[staff.assessment_level] ?? staff.assessment_level : '—'}
                  </td>
                  <td className="py-2 pr-3">
                    <Badge variant={staff.is_active ? 'navy' : 'neutral'}>{staff.is_active ? 'Active' : 'Deactivated'}</Badge>
                  </td>
                  <td className="py-2 text-right">
                    {staff.is_active ? (
                      <button
                        type="button"
                        disabled={busyStaffId === staff.id}
                        onClick={() => void handleDeactivate(staff)}
                        className="text-sm text-red-600 underline disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {busyStaffId === staff.id ? 'Working…' : 'Deactivate'}
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={busyStaffId === staff.id}
                        onClick={() => void handleReactivate(staff)}
                        className="text-sm text-brand-navy underline disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {busyStaffId === staff.id ? 'Working…' : 'Reactivate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {staffPage && staffRows.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-neutral-400">
                    No {statusFilter} staff found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {staffPage && staffPage.count > 0 && (
          <div className="mt-4 flex items-center justify-between text-sm text-neutral-500">
            <span>{staffPage.count} total</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled={!staffPage.previous} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={!staffPage.next} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
