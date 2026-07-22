interface PageNavFooterProps {
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  nextDisabled?: boolean
  nextDisabledReason?: string
  nextLabel?: string
}

export function PageNavFooter({
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  nextDisabled = false,
  nextDisabledReason,
  nextLabel,
}: PageNavFooterProps) {
  return (
    <div className="mt-6 flex items-center justify-between border-t border-slate-200 pt-4">
      <button
        type="button"
        onClick={onPrevious}
        disabled={!hasPrevious}
        className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        ← Previous
      </button>

      <div className="text-right">
        {nextDisabled && nextDisabledReason && <p className="mb-1 text-xs text-slate-400">{nextDisabledReason}</p>}
        <button
          type="button"
          onClick={onNext}
          disabled={!hasNext || nextDisabled}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {nextLabel ?? (hasNext ? 'Next →' : 'Finish')}
        </button>
      </div>
    </div>
  )
}
