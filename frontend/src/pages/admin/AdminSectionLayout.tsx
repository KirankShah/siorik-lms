import { NavLink, Outlet } from 'react-router-dom'

const subNavLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
  }`

export function AdminSectionLayout() {
  return (
    <div>
      <nav className="mb-6 flex items-center gap-1 border-b border-slate-200 pb-4">
        <NavLink to="/admin/courses" className={subNavLinkClass} end={false}>
          Courses
        </NavLink>
        <NavLink to="/admin/reports" className={subNavLinkClass}>
          Reports
        </NavLink>
        <NavLink to="/admin/bulk-enroll" className={subNavLinkClass}>
          Bulk Enroll
        </NavLink>
      </nav>
      <Outlet />
    </div>
  )
}
