import {
  Award,
  BarChart3,
  BookOpen,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  PanelLeftClose,
  Settings,
  Trophy,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import siorikLogo from '../../img/siorik_logo_icon.png'
import { useAuth } from '../../context/AuthContext'
import { isAdminRole, isOrgSettingsRole } from '../../lib/roles'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

interface SidebarProps {
  onNavigate?: () => void
  onCollapse?: () => void
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${
    isActive ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'
  }`

export function Sidebar({ onNavigate, onCollapse }: SidebarProps) {
  const { user, logout } = useAuth()
  const admin = isAdminRole(user?.role)

  const navItems: NavItem[] = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    // Admins land on the management table; everyone else gets the catalog —
    // both already exist, this just picks the useful one per role.
    { to: admin ? '/admin/courses' : '/courses', label: 'Courses', icon: BookOpen },
    { to: '/assessments', label: 'Assessments', icon: ClipboardList },
    { to: '/certificates', label: 'Certificates', icon: Award },
    { to: '/achievements', label: 'Achievements', icon: Trophy },
    // Admins get the cross-learner report; everyone else gets their own progress.
    { to: admin ? '/admin/reports' : '/reports', label: admin ? 'Reports' : 'My Reports', icon: BarChart3 },
  ]

  return (
    <div className="flex h-full w-64 flex-col bg-brand-navy">
      <div className="flex items-center justify-between gap-2 px-5 py-5">
        <div className="flex items-center gap-2">
          <img src={siorikLogo} alt="Siorik Consultancy" className="h-8 w-8 object-contain" />
          <span className="text-sm font-semibold tracking-wide text-white uppercase">Siorik</span>
        </div>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            aria-label="Hide sidebar"
            title="Hide sidebar"
            className="rounded p-1 text-white/50 transition hover:bg-white/10 hover:text-white"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={label} to={to} className={linkClass} onClick={onNavigate}>
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </NavLink>
        ))}

        {isOrgSettingsRole(user?.role) && (
          <>
            <NavLink to="/admin/learners" className={linkClass} onClick={onNavigate}>
              <Users className="h-[18px] w-[18px]" />
              Learners
            </NavLink>
            <NavLink to="/admin/organization" className={linkClass} onClick={onNavigate}>
              <Settings className="h-[18px] w-[18px]" />
              Organization Settings
            </NavLink>
          </>
        )}
      </nav>

      <div className="border-t border-white/10 px-3 py-4">
        <div className="px-3">
          <p className="truncate text-sm font-medium text-white">{user?.email}</p>
          <p className="text-xs text-white/50">{user?.role.replace('_', ' ')}</p>
        </div>
        <button
          type="button"
          onClick={logout}
          className="mt-3 flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-white/70 transition hover:bg-white/5 hover:text-white"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Log out
        </button>
      </div>
    </div>
  )
}
