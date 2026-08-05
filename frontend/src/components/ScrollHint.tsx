import { useEffect, useState, type RefObject } from 'react'
import { ChevronDown } from 'lucide-react'

// Tracks whether a scroll container currently has more content below the
// fold. `contentRef` (the element that actually grows/shrinks, e.g. an
// inner padded wrapper) is observed separately from `scrollRef` (the element
// with overflow-y set) because a fixed-height scroll container never
// resizes itself when its content does — only its scrollHeight changes,
// which a ResizeObserver on the container alone would never see.
export function useScrollOverflow(scrollRef: RefObject<HTMLElement | null>, contentRef: RefObject<HTMLElement | null>) {
  const [hasOverflow, setHasOverflow] = useState(false)
  const [atBottom, setAtBottom] = useState(true)

  useEffect(() => {
    const scrollEl = scrollRef.current
    if (!scrollEl) return

    function update() {
      if (!scrollEl) return
      setHasOverflow(scrollEl.scrollHeight - scrollEl.clientHeight > 1)
      setAtBottom(scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < 2)
    }

    update()
    scrollEl.addEventListener('scroll', update, { passive: true })
    const resizeObserver = new ResizeObserver(update)
    resizeObserver.observe(scrollEl)
    if (contentRef.current) resizeObserver.observe(contentRef.current)

    return () => {
      scrollEl.removeEventListener('scroll', update)
      resizeObserver.disconnect()
    }
  }, [scrollRef, contentRef])

  return { hasOverflow, atBottom }
}

interface ScrollHintProps {
  visible: boolean
  // A plain CSS color to fade toward, e.g. "#ffffff" — omitted when a slide
  // template's background isn't a simple color (a gradient/image string
  // can't be reused as a fade stop), in which case only the chevron badge
  // shows since it reads on any background.
  fadeColor?: string | null
}

// Bottom-of-scroll-region affordance: a soft fade (only when the background
// is a known flat color) plus a chevron badge (background-agnostic, so it's
// always the primary signal). Renders nothing once there's no more content
// below the fold, or none to begin with.
//
// Must be rendered as the LAST CHILD inside the scrolling element itself
// (not a sibling positioned over it) — it pins to the bottom edge via
// `sticky`, which affixes to the nearest scrolling ancestor's own viewport
// regardless of exactly how tall that ancestor ends up being. An earlier
// version sat outside the scroll container as an `absolute bottom-0`
// sibling instead, anchored to a wrapper div that was *supposed* to be
// exactly as tall as the scroll viewport — any mismatch there (and the
// fixed-canvas's height comes from several nested flex/aspect-ratio layers,
// easy to get slightly wrong) left the chevron floating wherever that
// wrapper's box actually ended, not at the true bottom edge. The outer div
// here is zero-height and sticky so it never adds scrollable space of its
// own; the inner div is absolutely positioned against *that* sticky box
// (itself a valid containing block) so its content renders growing upward
// from the sticky line instead of downward past the visible edge.
export function ScrollHint({ visible, fadeColor = null }: ScrollHintProps) {
  if (!visible) return null
  return (
    <div className="pointer-events-none sticky inset-x-0 bottom-0 z-10 h-0">
      <div className="absolute inset-x-0 bottom-0 flex justify-center">
        {fadeColor && (
          <div
            className="absolute inset-x-0 bottom-0 h-8"
            style={{ background: `linear-gradient(to top, ${fadeColor}, transparent)` }}
          />
        )}
        <div className="relative mb-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-white/90 shadow ring-1 ring-black/5">
          <ChevronDown className="h-3.5 w-3.5 animate-bounce text-neutral-500" />
        </div>
      </div>
    </div>
  )
}
