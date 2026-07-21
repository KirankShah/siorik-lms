import { useState } from 'react'
import { grantCourseAccess, revokeCourseAccess } from '../../lib/coursesApi'
import type { Organization } from '../../types/auth'
import type { CourseAccessGrant } from '../../types/courses'

interface AccessGrantsPanelProps {
  courseSlug: string
  grants: CourseAccessGrant[]
  organizations: Organization[]
  onChanged: () => void
}

export function AccessGrantsPanel({ courseSlug, grants, organizations, onChanged }: AccessGrantsPanelProps) {
  const [selectedOrgId, setSelectedOrgId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const grantedOrgIds = new Set(grants.map((grant) => grant.organization.id))
  const ungranted = organizations.filter((org) => !grantedOrgIds.has(org.id))

  async function handleGrant() {
    if (!selectedOrgId) return
    setIsSaving(true)
    setError(null)
    try {
      await grantCourseAccess(courseSlug, Number(selectedOrgId))
      setSelectedOrgId('')
      onChanged()
    } catch {
      setError('Could not grant access.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleRevoke(organizationId: number) {
    if (!window.confirm('Revoke this organization\'s access to the course?')) return
    try {
      await revokeCourseAccess(courseSlug, organizationId)
      onChanged()
    } catch {
      setError('Could not revoke access.')
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">Organization Access</h2>
      <p className="mt-1 text-xs text-slate-500">
        Platform-managed courses aren't visible to any organization until granted access here — a
        stand-in for the per-user billing step, which isn't automated yet.
      </p>

      <ul className="mt-3 space-y-2">
        {grants.map((grant) => (
          <li
            key={grant.id}
            className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 text-sm"
          >
            <span>
              {grant.organization.name}{' '}
              <span className="text-xs text-slate-400">
                since {new Date(grant.granted_at).toLocaleDateString()}
              </span>
            </span>
            <button
              type="button"
              onClick={() => handleRevoke(grant.organization.id)}
              className="text-red-600 hover:underline"
            >
              Revoke
            </button>
          </li>
        ))}
        {grants.length === 0 && <li className="text-sm text-slate-400">No organizations have access yet.</li>}
      </ul>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      {ungranted.length > 0 && (
        <div className="mt-3 flex items-center gap-2">
          <select
            value={selectedOrgId}
            onChange={(e) => setSelectedOrgId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">Select an organization…</option>
            {ungranted.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!selectedOrgId || isSaving}
            onClick={handleGrant}
            className="text-sm font-medium text-emerald-700 disabled:opacity-60"
          >
            {isSaving ? 'Granting…' : 'Grant access'}
          </button>
        </div>
      )}
    </div>
  )
}
