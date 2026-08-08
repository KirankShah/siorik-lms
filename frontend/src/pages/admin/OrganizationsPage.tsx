import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/apiClient'
import { createOrganization, fetchOrganizations } from '../../lib/accountsApi'
import type { Organization } from '../../types/auth'

export function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [createError, setCreateError] = useState<string | null>(null)
  const [createSuccess, setCreateSuccess] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

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

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Organizations</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Onboard a new client institution — its own admins and learners get added afterward via Demo Users.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
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
          <h2 className="text-sm font-semibold text-neutral-900">Existing organizations</h2>

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
                  <Badge variant={org.is_active ? 'navy' : 'neutral'}>{org.is_active ? 'Active' : 'Inactive'}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
