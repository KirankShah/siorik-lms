export interface HotspotRegionOption {
  id: number
  x: number
  y: number
  width: number
  height: number
}

interface HotspotAnswerProps {
  image: string
  regions: HotspotRegionOption[]
  selected: Set<number>
  onChange: (next: Set<number>) => void
}

// Regions are pre-drawn by the instructor (see HotspotEditor) — the learner
// just clicks the ones they believe are correct, no dragging involved.
export function HotspotAnswer({ image, regions, selected, onChange }: HotspotAnswerProps) {
  function toggle(regionId: number) {
    const next = new Set(selected)
    if (next.has(regionId)) next.delete(regionId)
    else next.add(regionId)
    onChange(next)
  }

  return (
    <div className="relative inline-block max-w-full">
      <img src={image} alt="" className="block max-w-full rounded border border-neutral-200" draggable={false} />
      {regions.map((region) => {
        const isSelected = selected.has(region.id)
        return (
          <button
            key={region.id}
            type="button"
            onClick={() => toggle(region.id)}
            aria-pressed={isSelected}
            aria-label="Mark this region"
            className={`absolute rounded-sm border-2 transition ${
              isSelected ? 'border-brand-navy bg-brand-navy/20' : 'border-transparent bg-transparent hover:border-brand-navy/40 hover:bg-brand-navy/5'
            }`}
            style={{ left: `${region.x}%`, top: `${region.y}%`, width: `${region.width}%`, height: `${region.height}%` }}
          >
            {isSelected && (
              <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-brand-navy text-xs text-white shadow">
                ✓
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
