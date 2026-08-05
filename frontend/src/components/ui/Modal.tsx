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
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
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
