import { NavLink, Outlet } from 'react-router-dom'
import siorikLogo from '../img/siorik_logo_icon.png'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium transition ${
    isActive ? 'bg-brand-navy text-white' : 'text-neutral-600 hover:bg-neutral-100'
  }`

const ADMIN_ROLES = ['INSTRUCTOR', 'ORG_ADMIN', 'PLATFORM_ADMIN']

export function AppLayout() {
  const { user, logout } = useAuth()
  const isAdmin = !!user && ADMIN_ROLES.includes(user.role)

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <img src={siorikLogo} alt="Siorik Consultancy" className="h-8 w-8 object-contain" />
              <span className="text-sm font-semibold tracking-wide text-brand-navy uppercase">Siorik</span>
            </div>
            <nav className="flex items-center gap-1">
              <NavLink to="/dashboard" className={navLinkClass}>
                Dashboard
              </NavLink>
              <NavLink to="/courses" className={navLinkClass}>
                Courses
              </NavLink>
              <NavLink to="/certificates" className={navLinkClass}>
                Certificates
              </NavLink>
              {isAdmin && (
                <NavLink to="/admin/courses" className={navLinkClass}>
                  Admin
                </NavLink>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-neutral-500">{user?.email}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
