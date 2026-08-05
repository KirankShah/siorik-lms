import type { ImageColumnWidth } from '../../types/slides'

const WIDTHS: { value: ImageColumnWidth; label: string; percent: string }[] = [
  { value: 'COMPACT', label: 'Compact', percent: '35%' },
  { value: 'STANDARD', label: 'Standard', percent: '45%' },
  { value: 'WIDE', label: 'Wide', percent: '55%' },
]

// Caps how wide the IMAGE_LEFT/IMAGE_RIGHT docked image column can grow —
// the image still auto-sizes to its own aspect ratio up to that cap, this
// only raises or lowers the ceiling. Only meaningful (and only rendered by
// SlideCard) when the slide's layout is actually IMAGE_LEFT/IMAGE_RIGHT.
export function ImageWidthPicker({
  value,
  onChange,
}: {
  value: ImageColumnWidth
  onChange: (width: ImageColumnWidth) => void
}) {
  return (
    <div className="flex gap-1.5">
      {WIDTHS.map(({ value: width, label, percent }) => (
        <button
          key={width}
          type="button"
          onClick={() => onChange(width)}
          aria-pressed={value === width}
          title={`${label} (${percent})`}
          className={`rounded-md border px-2.5 py-1.5 text-xs font-medium transition ${
            value === width
              ? 'border-brand-navy bg-brand-navy/10 text-brand-navy'
              : 'border-neutral-200 text-neutral-500 hover:border-neutral-300 hover:text-neutral-700'
          }`}
        >
          {label}
          <span className={value === width ? 'ml-1 text-brand-navy/70' : 'ml-1 text-neutral-400'}>{percent}</span>
        </button>
      ))}
    </div>
  )
}
