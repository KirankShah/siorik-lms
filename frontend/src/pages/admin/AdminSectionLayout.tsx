import { NavLink, Outlet } from 'react-router-dom'

const subNavLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition ${
    isActive ? 'bg-brand-navy text-white' : 'text-neutral-600 hover:bg-neutral-100'
  }`

export function AdminSectionLayout() {
  return (
    <div>
      <nav className="mb-6 flex items-center gap-1 border-b border-neutral-200 pb-4">
        <NavLink to="/admin/courses" className={subNavLinkClass} end={false}>
          Courses
        </NavLink>
        <NavLink to="/admin/grading" className={subNavLinkClass}>
          Grading
        </NavLink>
        <NavLink to="/admin/reports" className={subNavLinkClass}>
          Reports
        </NavLink>
        <NavLink to="/admin/analytics" className={subNavLinkClass}>
          Analytics
        </NavLink>
        <NavLink to="/admin/bulk-enroll" className={subNavLinkClass}>
          Bulk Enroll
        </NavLink>
        <NavLink to="/admin/certificate-templates" className={subNavLinkClass}>
          Certificate Templates
        </NavLink>
        <NavLink to="/admin/demo-users" className={subNavLinkClass}>
          Demo Users
        </NavLink>
      </nav>
      <Outlet />
    </div>
  )
}
