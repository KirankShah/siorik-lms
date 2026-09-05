import type { ReactNode } from 'react'

interface SlideCanvasProps {
  fullscreen: boolean
  children: ReactNode
  // Fullscreen only. Shrinks the 80vh budget below by this many px so a
  // fixed-height bar docked below the canvas (currently only
  // player/NarrationPlayer, via ContentSlidePlayer) has genuine room in the
  // fullscreen overlay's non-scrolling content well instead of forcing the
  // canvas box to overflow it and get clipped — see
  // NarrationPlayer.NARRATION_BAR_FULLSCREEN_RESERVE_PX. 0 (the default)
  // reproduces the previous behavior exactly.
  bottomInsetPx?: number
}

// Fixed 16:9 slide frame for the learner-facing CONTENT player — standard
// and fullscreen only, never the admin authoring preview (SlideCard), which
// stays a flexible, flowing card. Every slide in a course gets the exact
// same canvas box regardless of how much content it holds; layout/scroll
// behavior inside it is SlideElementsView's job (see its canvasMode prop),
// this component only owns the box's size, position, and clipping.
export function SlideCanvas({ fullscreen, children, bottomInsetPx = 0 }: SlideCanvasProps) {
  if (fullscreen) {
    const heightBudget = bottomInsetPx > 0 ? `calc(80vh - ${bottomInsetPx}px)` : '80vh'
    return (
      // No manual padding here on purpose: max-width/max-height cap the box
      // to 80% of the viewport and this flex centers it, so the leftover
      // 20% splits evenly into equal margins on all four sides for free.
      // Adding padding on top of that was what made the old fullscreen view
      // lopsided.
      <div className="flex h-full w-full items-center justify-center overflow-hidden">
        <div
          className="slide-canvas relative overflow-hidden rounded-lg border border-black/10 bg-white shadow-lg"
          style={{
            aspectRatio: '16 / 9',
            // Fit the largest 16:9 box inside 80vw x heightBudget: whichever
            // of the two caps is tighter for this viewport wins, and the
            // other dimension follows from the ratio — plain
            // max-width/max-height can't do this because they leave the
            // *other* axis unconstrained.
            width: `min(80vw, calc(${heightBudget} * 16 / 9))`,
            height: `min(${heightBudget}, calc(80vw * 9 / 16))`,
          }}
        >
          {children}
        </div>
      </div>
    )
  }

  return (
    // 90% of whatever contains this (the Card's content area) rather than a
    // fixed pixel cap — every slide still gets the exact same box for a
    // given viewport/sidebar state, it just now actually uses the space
    // instead of floating a small card in a mostly-empty content area.
    // Height is never set directly; aspect-ratio derives it from the
    // resolved width, so the ratio stays locked at every size.
    <div
      className="slide-canvas relative mx-auto overflow-hidden rounded-lg border border-neutral-200 bg-white"
      style={{ aspectRatio: '16 / 9', width: '90%' }}
    >
      {children}
    </div>
  )
}
