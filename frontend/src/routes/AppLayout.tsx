import { useState } from 'react'
import { Menu, PanelLeftOpen, X } from 'lucide-react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from '../components/shell/Sidebar'
import siorikLogo from '../img/siorik_logo_icon.png'

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="flex min-h-screen bg-neutral-50">
      {/* Desktop sidebar — a real flex sibling (sticky, not fixed-positioned),
          so the content column reflows to fill the freed space automatically
          when it collapses, rather than relying on a margin/padding value
          kept in sync with the sidebar's width. `sticky` (instead of `fixed`)
          keeps it pinned while the page scrolls without taking it out of the
          flex flow the way `fixed` does. */}
      <div className="no-print sticky top-0 hidden h-screen shrink-0 lg:block">
        {sidebarCollapsed ? (
          <button
            type="button"
            onClick={() => setSidebarCollapsed(false)}
            aria-label="Show sidebar"
            title="Show sidebar"
            className="flex h-full w-8 flex-col items-center bg-brand-navy pt-5 text-white/60 transition-colors hover:text-white"
          >
            <PanelLeftOpen className="h-5 w-5" />
          </button>
        ) : (
          <Sidebar onCollapse={() => setSidebarCollapsed(true)} />
        )}
      </div>

      {/* Mobile drawer — stays a fixed overlay, outside the flex flow */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setMobileOpen(false)}
              className="absolute top-4 -right-11 rounded-md bg-white/10 p-2 text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-neutral-200 bg-white px-4 py-3 lg:hidden">
          <button type="button" aria-label="Open menu" onClick={() => setMobileOpen(true)} className="text-neutral-600">
            <Menu className="h-6 w-6" />
          </button>
          <img src={siorikLogo} alt="Siorik Consultancy" className="h-7 w-7 object-contain" />
          <span className="text-sm font-semibold tracking-wide text-brand-navy uppercase">Siorik</span>
        </header>

        {/* No mx-auto/max-w cap here — pages get the full width remaining
            after the sidebar, with just small consistent edge padding. Pages
            that want a narrower reading column (forms, tables) can apply
            their own max-width internally. */}
        <main className="flex-1 px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
