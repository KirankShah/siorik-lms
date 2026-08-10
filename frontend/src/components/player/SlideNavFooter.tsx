import { Button } from '../ui/Button'

interface SlideNavFooterProps {
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  nextDisabled?: boolean
  secondsRemaining?: number
  nextLabel?: string
  // Explains why Next is disabled (e.g. "Submit your answer to continue.")
  // for gates that aren't self-explanatory the way the dwell countdown text
  // already is. A `title` on a disabled <button> doesn't reliably tooltip
  // across browsers, so this wraps the button in a plain span instead.
  nextDisabledReason?: string
}

export function SlideNavFooter({
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  nextDisabled = false,
  secondsRemaining = 0,
  nextLabel,
  nextDisabledReason,
}: SlideNavFooterProps) {
  const nextButton = (
    <Button onClick={onNext} disabled={!hasNext || nextDisabled}>
      {nextLabel ?? (hasNext ? 'Next →' : 'Finish')}
    </Button>
  )

  return (
    <div className="no-print mt-6 flex items-center justify-between border-t border-neutral-200 pt-4">
      <Button variant="outline" onClick={onPrevious} disabled={!hasPrevious}>
        ← Previous
      </Button>

      <div className="text-right">
        {nextDisabled && secondsRemaining > 0 && (
          <p className="mb-1 text-xs text-neutral-400">Keep reading — available in {secondsRemaining}s</p>
        )}
        {nextDisabled && nextDisabledReason ? <span title={nextDisabledReason}>{nextButton}</span> : nextButton}
      </div>
    </div>
  )
}
