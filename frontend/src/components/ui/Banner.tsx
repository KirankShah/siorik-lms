import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export type BannerVariant = 'info' | 'success' | 'warning' | 'gold'

export interface BannerProps {
  variant?: BannerVariant
  title?: string
  children?: ReactNode
  action?: ReactNode
  onDismiss?: () => void
  className?: string
}

const VARIANT_CLASSES: Record<BannerVariant, string> = {
  info: 'border-brand-navy/15 bg-brand-navy/5 text-brand-navy',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  gold: 'border-brand-gold/40 bg-brand-gold/10 text-brand-navy',
}

// Generic top-of-page notice slot — same component for a one-off welcome
// message today and trial-status/announcement banners later; callers own the
// content and decide when to render it.
export function Banner({ variant = 'info', title, children, action, onDismiss, className = '' }: BannerProps) {
  return (
    <div
      role="status"
      className={`flex items-start justify-between gap-4 rounded-xl border px-4 py-3 text-sm ${VARIANT_CLASSES[variant]} ${className}`}
    >
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-0.5' : ''}>{children}</div>}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {action}
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss"
            className="rounded p-1 text-current opacity-70 transition hover:bg-black/5 hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )
}
