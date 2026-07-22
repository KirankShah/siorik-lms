import { useState } from 'react'
import type { ReactNode } from 'react'
import './collapsible.css'

interface ToggleWrapperProps {
  header: ReactNode
  defaultOpen?: boolean
  accentClassName?: string
}

// Shared collapsible header used by both the Accordion and FAQ blocks. The
// header (block's own inline content) stays here; the expandable body is
// whatever child blocks the instructor nests underneath — see collapsible.css
// for how those get hidden/shown.
export function ToggleWrapper({ header, defaultOpen = true, accentClassName }: ToggleWrapperProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="lms-toggle-wrapper flex w-full items-start gap-1.5 py-0.5" data-show-children={open ? 'true' : 'false'}>
      <button
        type="button"
        contentEditable={false}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => setOpen((v) => !v)}
        className={`mt-1 shrink-0 rounded p-0.5 text-slate-400 transition hover:bg-slate-100 ${accentClassName ?? ''}`}
        aria-label={open ? 'Collapse' : 'Expand'}
      >
        <svg viewBox="0 0 20 20" className={`h-4 w-4 transition-transform ${open ? 'rotate-90' : ''}`} fill="currentColor">
          <path d="M7 5l6 5-6 5V5z" />
        </svg>
      </button>
      <div className="min-w-0 flex-1">{header}</div>
    </div>
  )
}
