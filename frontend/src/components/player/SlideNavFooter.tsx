import { Button } from '../ui/Button'

interface SlideNavFooterProps {
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  nextDisabled?: boolean
  secondsRemaining?: number
  nextLabel?: string
}

export function SlideNavFooter({
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  nextDisabled = false,
  secondsRemaining = 0,
  nextLabel,
}: SlideNavFooterProps) {
  return (
    <div className="no-print mt-6 flex items-center justify-between border-t border-neutral-200 pt-4">
      <Button variant="outline" onClick={onPrevious} disabled={!hasPrevious}>
        ← Previous
      </Button>

      <div className="text-right">
        {nextDisabled && secondsRemaining > 0 && (
          <p className="mb-1 text-xs text-neutral-400">Keep reading — available in {secondsRemaining}s</p>
        )}
        <Button onClick={onNext} disabled={!hasNext || nextDisabled}>
          {nextLabel ?? (hasNext ? 'Next →' : 'Finish')}
        </Button>
      </div>
    </div>
  )
}
