import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useOutletContext } from 'react-router-dom'
import { AccessGrantsPanel } from '../../components/admin/AccessGrantsPanel'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { useAuth } from '../../context/AuthContext'
import { fetchOrganizations } from '../../lib/accountsApi'
import { ApiError } from '../../lib/apiClient'
import { bulkEnroll, inviteLearnerByEmail } from '../../lib/coursesApi'
import type { BulkEnrollResult } from '../../types/admin'
import type { Organization } from '../../types/auth'
import type { CourseDashboardContext } from './CourseDashboardLayout'

function isDetailBody(body: unknown): body is { detail: string } {
  return typeof body === 'object' && body !== null && typeof (body as { detail?: unknown }).detail === 'string'
}

function EmailList({ label, emails }: { label: string; emails: string[] }) {
  if (emails.length === 0) return null
  return (
    <p className="text-sm text-neutral-600">
      <span className="font-medium text-neutral-900">{label}:</span> {emails.join(', ')}
    </p>
  )
}

export function CourseShareTab() {
  const { course, reload } = useOutletContext<CourseDashboardContext>()
  const { user } = useAuth()
  const isPlatformAdmin = user?.role === 'PLATFORM_ADMIN'
  const [organizations, setOrganizations] = useState<Organization[]>([])

  useEffect(() => {
    if (isPlatformAdmin) fetchOrganizations().then(setOrganizations).catch(() => {})
  }, [isPlatformAdmin])

  const [email, setEmail] = useState('')
  const [isInviting, setIsInviting] = useState(false)
  const [inviteStatus, setInviteStatus] = useState<string | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)

  async function handleInvite(event: FormEvent) {
    event.preventDefault()
    setIsInviting(true)
    setInviteError(null)
    setInviteStatus(null)
    try {
      const result = await inviteLearnerByEmail(course.slug, email)
      setInviteStatus(result.created ? `Enrolled ${result.email}.` : `${result.email} was already enrolled.`)
      setEmail('')
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setInviteError(`No account found for ${email}.`)
      } else if (err instanceof ApiError && err.status === 400 && isDetailBody(err.body)) {
        setInviteError(err.body.detail)
      } else {
        setInviteError('Could not invite this learner.')
      }
    } finally {
      setIsInviting(false)
    }
  }

  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [isBulkEnrolling, setIsBulkEnrolling] = useState(false)
  const [bulkResult, setBulkResult] = useState<BulkEnrollResult | null>(null)
  const [bulkError, setBulkError] = useState<string | null>(null)

  async function handleBulkEnroll() {
    if (!csvFile) return
    setIsBulkEnrolling(true)
    setBulkError(null)
    setBulkResult(null)
    try {
      const result = await bulkEnroll(course.slug, csvFile)
      setBulkResult(result)
      setCsvFile(null)
    } catch {
      setBulkError('Could not process this CSV file.')
    } finally {
      setIsBulkEnrolling(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-sm font-semibold text-neutral-900">Invite a learner</h2>
        <p className="mt-1 text-sm text-neutral-500">Enroll one learner by email — they must already have an account.</p>

        <form onSubmit={handleInvite} className="mt-4 flex flex-wrap items-end gap-3">
          <div className="w-64">
            <Input
              id="invite-email"
              label="Email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={isInviting}>
            {isInviting ? 'Inviting…' : 'Invite'}
          </Button>
        </form>

        {inviteStatus && <p className="mt-2 text-sm text-emerald-600">{inviteStatus}</p>}
        {inviteError && <p className="mt-2 text-sm text-red-600">{inviteError}</p>}
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-neutral-900">Bulk enroll via CSV</h2>
        <p className="mt-1 text-sm text-neutral-500">
          A CSV with one existing account email per row. Unmatched emails are reported, not created.
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <Button size="sm" disabled={!csvFile || isBulkEnrolling} onClick={handleBulkEnroll}>
            {isBulkEnrolling ? 'Enrolling…' : 'Enroll learners'}
          </Button>
        </div>

        {bulkError && <p className="mt-2 text-sm text-red-600">{bulkError}</p>}
        {bulkResult && (
          <div className="mt-3 space-y-1">
            <EmailList label="Enrolled" emails={bulkResult.enrolled} />
            <EmailList label="Already enrolled" emails={bulkResult.already_enrolled} />
            <EmailList label="Not found" emails={bulkResult.not_found} />
            <EmailList label="Different organization" emails={bulkResult.wrong_organization} />
          </div>
        )}
      </Card>

      {isPlatformAdmin && course.content_owner === 'PLATFORM' && (
        <AccessGrantsPanel
          courseSlug={course.slug}
          grants={course.access_grants}
          organizations={organizations}
          onChanged={reload}
        />
      )}
    </div>
  )
}
