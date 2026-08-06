import { useEffect, useState } from 'react'
import { ChevronRight, ExternalLink } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useParams } from 'react-router-dom'
import { fetchCourseDetail } from '../../lib/coursesApi'
import type { CourseDetail } from '../../types/courses'

const TABS = [
  { to: 'slides', label: 'Slides' },
  { to: 'settings', label: 'Settings' },
  { to: 'certification', label: 'Certification' },
  { to: 'demo-access', label: 'Demo Access' },
  { to: 'share', label: 'Share' },
  { to: 'analyze', label: 'Analyze' },
]

export interface CourseDashboardContext {
  course: CourseDetail
  reload: () => void
}

export function CourseDashboardLayout() {
  const { slug } = useParams<{ slug: string }>()
  const location = useLocation()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    if (!slug) return
    fetchCourseDetail(slug)
      .then(setCourse)
      .catch(() => setError('Could not load this course.'))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [slug])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!course) return <p className="text-sm text-neutral-500">Loading course…</p>

  const activeTab = TABS.find((tab) => location.pathname.endsWith(`/${tab.to}`))

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-200 pb-4">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-neutral-500">
          <Link to="/dashboard" className="hover:text-neutral-900 hover:underline">
            Dashboard
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <Link to="/admin/courses" className="hover:text-neutral-900 hover:underline">
            Courses
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="font-medium text-neutral-900">{course.title}</span>
          {activeTab && (
            <>
              <ChevronRight className="h-3.5 w-3.5" />
              <span>{activeTab.label}</span>
            </>
          )}
        </nav>

        <a
          href={`/courses/${course.slug}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md border border-brand-navy px-3 py-1.5 text-sm font-medium text-brand-navy transition hover:bg-brand-navy hover:text-white"
        >
          View course
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>

      <div className="mt-6 flex flex-col gap-8 lg:flex-row">
        <nav className="flex shrink-0 gap-1 overflow-x-auto lg:w-44 lg:flex-col lg:overflow-visible">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `shrink-0 rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap transition ${
                  isActive ? 'bg-brand-navy/10 text-brand-navy' : 'text-neutral-600 hover:bg-neutral-100'
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>

        <div className="min-w-0 flex-1">
          <Outlet context={{ course, reload: load } satisfies CourseDashboardContext} />
        </div>
      </div>
    </div>
  )
}
