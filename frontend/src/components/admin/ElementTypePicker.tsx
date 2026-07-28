import { Modal } from '../ui/Modal'
import { ELEMENT_TYPE_ICON, ELEMENT_TYPE_LABEL, ELEMENT_TYPES } from '../../lib/elementTypes'
import type { ElementType } from '../../types/slides'

interface ElementTypePickerProps {
  onPick: (type: ElementType) => void
  onClose: () => void
}

export function ElementTypePicker({ onPick, onClose }: ElementTypePickerProps) {
  return (
    <Modal title="Add new element" onClose={onClose} widthClassName="max-w-xl">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {ELEMENT_TYPES.map((type) => {
          const Icon = ELEMENT_TYPE_ICON[type]
          return (
            <button
              key={type}
              type="button"
              onClick={() => onPick(type)}
              className="flex flex-col items-center gap-2 rounded-lg border border-neutral-200 p-4 text-center text-xs font-medium text-neutral-700 transition hover:border-brand-navy hover:bg-brand-navy/5 hover:text-brand-navy"
            >
              <Icon className="h-5 w-5" />
              {ELEMENT_TYPE_LABEL[type]}
            </button>
          )
        })}
      </div>
    </Modal>
  )
}
