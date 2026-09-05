import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  widthClassName?: string
  maxHeightClassName?: string
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  widthClassName = 'max-w-lg',
  maxHeightClassName = 'max-h-[85vh]',
}: ModalProps) {
  // Escape closes any modal in the app the same way its own X button does —
  // every caller already passes the same handler to both, so this adds no
  // new way for a modal to close, just a standard extra path to the
  // existing one.
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    // z-[110]: a dialog must always sit above every other overlay in the
    // app, including FullscreenSlideOverlay's z-[100] — otherwise a modal
    // triggered while fullscreen (e.g. CourseCompletionModal) renders but is
    // stacked invisibly underneath it.
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className={`relative flex ${maxHeightClassName} w-full ${widthClassName} flex-col overflow-hidden rounded-xl bg-white shadow-xl`}>
        <div className="flex items-center justify-between border-b border-neutral-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-neutral-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-neutral-400 transition hover:bg-neutral-100 hover:text-neutral-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex shrink-0 justify-end gap-3 border-t border-neutral-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}
