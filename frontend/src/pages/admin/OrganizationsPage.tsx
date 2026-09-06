import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/apiClient'
import { createOrgAdmin, createOrganization, deleteOrganization, fetchOrganizations } from '../../lib/accountsApi'
import type { Organization } from '../../types/auth'

export function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const [name, setName] = useState('')
  const [createError, setCreateError] = useState<string | null>(null)
  const [createSuccess, setCreateSuccess] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [adminOrgId, setAdminOrgId] = useState('')
  const [adminName, setAdminName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [adminError, setAdminError] = useState<string | null>(null)
  const [adminSuccess, setAdminSuccess] = useState<string | null>(null)
  const [isSubmittingAdmin, setIsSubmittingAdmin] = useState(false)

  function loadOrganizations() {
    fetchOrganizations()
      .then(setOrganizations)
      .catch(() => setListError('Could not load organizations.'))
  }

  useEffect(loadOrganizations, [])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setCreateError(null)
    setCreateSuccess(null)
    setIsSubmitting(true)
    try {
      const organization = await createOrganization({ name })
      setCreateSuccess(`Created "${organization.name}".`)
      setName('')
      loadOrganizations()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string; name?: string[] } | null
        setCreateError(body?.detail ?? body?.name?.[0] ?? 'Could not create this organization.')
      } else {
        setCreateError('Could not create this organization.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDelete(organization: Organization) {
    if (
      !window.confirm(
        `Delete "${organization.name}"? This permanently deletes all of its users and all of its own courses too. This cannot be undone.`
      )
    ) {
      return
    }
    setDeletingId(organization.id)
    setListError(null)
    try {
      await deleteOrganization(organization.id)
      loadOrganizations()
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string } | null
        setListError(body?.detail ?? 'Could not delete this organization.')
      } else {
        setListError('Could not delete this organization.')
      }
    } finally {
      setDeletingId(null)
    }
  }

  async function handleAdminSubmit(event: FormEvent) {
    event.preventDefault()
    if (!adminOrgId) return
    setAdminError(null)
    setAdminSuccess(null)
    setIsSubmittingAdmin(true)
    try {
      const user = await createOrgAdmin({ name: adminName, email: adminEmail, organization: Number(adminOrgId) })
      setAdminSuccess(`Invite sent to ${user.email}.`)
      setAdminName('')
      setAdminEmail('')
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const body = err.body as { detail?: string; email?: string[] } | null
        setAdminError(body?.detail ?? body?.email?.[0] ?? 'Could not create this admin account.')
      } else {
        setAdminError('Could not create this admin account.')
      }
    } finally {
      setIsSubmittingAdmin(false)
    }
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Organizations</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Onboard a new client institution, then add its administrator(s) — learners get added afterward via Demo Users.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <h2 className="text-sm font-semibold text-neutral-900">Create an organization</h2>
            <form onSubmit={handleSubmit} className="mt-4 space-y-4">
              <Input id="org-name" label="Name" required value={name} onChange={(e) => setName(e.target.value)} />

              {createError && <p className="text-sm text-red-600">{createError}</p>}
              {createSuccess && <p className="text-sm text-emerald-700">{createSuccess}</p>}

              <Button type="submit" disabled={isSubmitting || !name.trim()}>
                {isSubmitting ? 'Creating…' : 'Create organization'}
              </Button>
            </form>
          </Card>

          <Card>
            <h2 className="text-sm font-semibold text-neutral-900">Add an organization admin</h2>
            <p className="mt-1 text-xs text-neutral-500">
              Creates a real administrator account for the selected organization and emails them an invite.
            </p>
            <form onSubmit={handleAdminSubmit} className="mt-4 space-y-4">
              <div>
                <label htmlFor="admin-org" className="block text-sm font-medium text-neutral-700">
                  Organization
                </label>
                <select
                  id="admin-org"
                  required
                  value={adminOrgId}
                  onChange={(e) => setAdminOrgId(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm"
                >
                  <option value="">Select an organization…</option>
                  {organizations?.map((org) => (
                    <option key={org.id} value={org.id}>
                      {org.name}
                    </option>
                  ))}
                </select>
              </div>
              <Input id="admin-name" label="Name" required value={adminName} onChange={(e) => setAdminName(e.target.value)} />
              <Input
                id="admin-email"
                label="Email"
                type="email"
                required
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
              />

              {adminError && <p className="text-sm text-red-600">{adminError}</p>}
              {adminSuccess && <p className="text-sm text-emerald-700">{adminSuccess}</p>}

              <Button type="submit" disabled={isSubmittingAdmin || !adminOrgId}>
                {isSubmittingAdmin ? 'Creating…' : 'Create admin and send invite'}
              </Button>
            </form>
          </Card>
        </div>

        <Card>
          <h2 className="text-sm font-semibold text-neutral-900">Existing organizations</h2>
          <p className="mt-1 text-xs text-neutral-500">
            Deleting an organization also permanently deletes all of its users and all of its own courses (including
            any cloned into it). This cannot be undone.
          </p>

          {listError && <p className="mt-4 text-sm text-red-600">{listError}</p>}

          {!organizations ? (
            <p className="mt-4 text-sm text-neutral-500">Loading…</p>
          ) : organizations.length === 0 ? (
            <p className="mt-4 text-sm text-neutral-500">No organizations yet.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {organizations.map((org) => (
                <li key={org.id} className="flex items-center justify-between gap-3 rounded-md border border-neutral-200 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-neutral-900">{org.name}</p>
                    <p className="text-xs text-neutral-500">/{org.slug}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={org.is_active ? 'navy' : 'neutral'}>{org.is_active ? 'Active' : 'Inactive'}</Badge>
                    <button
                      type="button"
                      disabled={deletingId === org.id}
                      onClick={() => void handleDelete(org)}
                      className="text-sm text-red-600 underline disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {deletingId === org.id ? 'Deleting…' : 'Delete'}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
