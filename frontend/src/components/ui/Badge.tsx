import type { HTMLAttributes } from 'react'

export type BadgeVariant = 'neutral' | 'navy' | 'gold' | 'dark'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: 'bg-neutral-100 text-neutral-700',
  navy: 'bg-brand-navy/10 text-brand-navy',
  gold: 'bg-brand-gold/20 text-brand-navy',
  // For use on the navy gradient panel (login left panel, etc).
  dark: 'border border-white/25 bg-white/10 text-white',
}

export function Badge({ variant = 'neutral', className = '', ...props }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  )
}
