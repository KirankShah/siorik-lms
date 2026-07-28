import type { ReactNode } from 'react'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, X } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import type { FlatSlideEntry } from '../../lib/slideSequence'

interface FullscreenSlideOverlayProps {
  activeEntry: FlatSlideEntry
  children: ReactNode
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  nextDisabled: boolean
  secondsRemaining: number
  isAtFirst: boolean
  isAtLast: boolean
  onGoToFirst: () => void
  onGoToLast: () => void
  onExit: () => void
}

// Full-viewport focus mode for a single slide. Deliberately reuses <Card> for
// the content well so every element type renders pixel-identical to the
// standard view — this overlay only changes the chrome around it, never the
// slide content itself.
export function FullscreenSlideOverlay({
  activeEntry,
  children,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  nextDisabled,
  secondsRemaining,
  isAtFirst,
  isAtLast,
  onGoToFirst,
  onGoToLast,
  onExit,
}: FullscreenSlideOverlayProps) {
  return (
    <div className="fixed inset-0 z-[100] flex flex-col bg-gradient-to-br from-brand-navy-tint-1 to-brand-navy-tint-2">
      <div className="flex shrink-0 items-center justify-between px-6 py-4">
        <p className="text-xs font-medium text-neutral-600">
          {activeEntry.module.title} / {activeEntry.lesson.title}
        </p>
        <button
          type="button"
          onClick={onExit}
          aria-label="Exit fullscreen"
          title="Exit fullscreen (Esc)"
          className="rounded-md p-2 text-neutral-500 transition hover:bg-black/5 hover:text-neutral-800"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* justify-center (not just mx-auto on the Card) keeps the card centered
          even if a descendant briefly forces this container wider than the
          viewport — items-start keeps it pinned to the top on tall content
          rather than fighting the scroll region for vertical centering. */}
      <div className="flex flex-1 items-start justify-center overflow-x-hidden overflow-y-auto px-6 pb-6">
        <Card className="w-full max-w-4xl">{children}</Card>
      </div>

      <div className="shrink-0 border-t border-black/10 bg-white/60 px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onGoToFirst}
              disabled={isAtFirst}
              aria-label="Go to first slide"
              title="Go to first slide"
              className="rounded-md p-2 text-neutral-500 transition hover:bg-black/5 hover:text-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronsLeft className="h-4 w-4" />
            </button>
            <Button variant="outline" size="sm" onClick={onPrevious} disabled={!hasPrevious}>
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
          </div>

          {nextDisabled && secondsRemaining > 0 && (
            <p className="text-xs text-neutral-500">Keep reading — available in {secondsRemaining}s</p>
          )}

          <div className="flex items-center gap-1">
            <Button size="sm" onClick={onNext} disabled={!hasNext || nextDisabled}>
              {hasNext ? 'Next' : 'Finish'}
              <ChevronRight className="h-4 w-4" />
            </Button>
            <button
              type="button"
              onClick={onGoToLast}
              disabled={isAtLast}
              aria-label="Go to last slide"
              title="Go to last reached slide"
              className="rounded-md p-2 text-neutral-500 transition hover:bg-black/5 hover:text-neutral-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronsRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
