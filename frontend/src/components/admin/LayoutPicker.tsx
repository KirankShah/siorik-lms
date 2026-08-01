import type { Layout } from '../../types/slides'

const LAYOUTS: { value: Layout; label: string }[] = [
  { value: 'STACKED', label: 'Stacked' },
  { value: 'IMAGE_LEFT', label: 'Image left' },
  { value: 'IMAGE_RIGHT', label: 'Image right' },
]

function LayoutShape({ layout }: { layout: Layout }) {
  if (layout === 'STACKED') {
    return (
      <svg viewBox="0 0 32 24" className="h-5 w-7">
        <rect x="1" y="1" width="30" height="22" rx="2" className="fill-none stroke-current" strokeWidth="1.5" />
        <rect x="5" y="6" width="22" height="3" className="fill-current" />
        <rect x="5" y="12" width="22" height="3" className="fill-current" />
        <rect x="5" y="18" width="14" height="3" className="fill-current" />
      </svg>
    )
  }

  const imageX = layout === 'IMAGE_LEFT' ? 3 : 19
  const textX = layout === 'IMAGE_LEFT' ? 17 : 3

  return (
    <svg viewBox="0 0 32 24" className="h-5 w-7">
      <rect x="1" y="1" width="30" height="22" rx="2" className="fill-none stroke-current" strokeWidth="1.5" />
      <rect x={imageX} y="4" width="10" height="16" rx="1" className="fill-current" />
      <rect x={textX} y="6" width="12" height="3" className="fill-current opacity-60" />
      <rect x={textX} y="12" width="12" height="3" className="fill-current opacity-60" />
      <rect x={textX} y="18" width="8" height="3" className="fill-current opacity-60" />
    </svg>
  )
}

export function LayoutPicker({ value, onChange }: { value: Layout; onChange: (layout: Layout) => void }) {
  return (
    <div className="flex gap-1.5">
      {LAYOUTS.map(({ value: layout, label }) => (
        <button
          key={layout}
          type="button"
          onClick={() => onChange(layout)}
          aria-label={label}
          aria-pressed={value === layout}
          title={label}
          className={`rounded-md border p-1.5 transition ${
            value === layout
              ? 'border-brand-navy bg-brand-navy/10 text-brand-navy'
              : 'border-neutral-200 text-neutral-400 hover:border-neutral-300 hover:text-neutral-600'
          }`}
        >
          <LayoutShape layout={layout} />
        </button>
      ))}
    </div>
  )
}
