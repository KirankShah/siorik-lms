import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { useAuth } from '../../context/AuthContext'

export function OrganizationSettingsPage() {
  const { user } = useAuth()
  const organization = user?.organization

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Organization Settings</h1>

      {!organization ? (
        <Card className="mt-6">
          <p className="text-sm text-neutral-500">
            {user?.role === 'PLATFORM_ADMIN'
              ? 'Platform admins are not scoped to a single organization — manage per-organization course access from a course’s access grants.'
              : 'No organization is associated with your account.'}
          </p>
        </Card>
      ) : (
        <Card className="mt-6 flex items-start gap-5">
          {organization.logo ? (
            <img src={organization.logo} alt="" className="h-16 w-16 rounded-lg object-contain" />
          ) : (
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-brand-navy/10 text-lg font-semibold text-brand-navy">
              {organization.name.slice(0, 2).toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-base font-semibold text-neutral-900">{organization.name}</p>
            <p className="text-sm text-neutral-500">/{organization.slug}</p>
            <Badge variant={organization.is_active ? 'navy' : 'neutral'} className="mt-3">
              {organization.is_active ? 'Active' : 'Inactive'}
            </Badge>
          </div>
        </Card>
      )}
    </div>
  )
}
