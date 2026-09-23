import { useState } from 'react'
import type { ReactNode } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCenter,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'

export interface MatchItem {
  id: number
  text: string
}

export interface MatchTargetOption {
  id: number
  text: string
}

interface MatchingAnswerProps {
  items: MatchItem[]
  targets: MatchTargetOption[]
  // targetId -> the id of the item currently dropped on it.
  assignments: Record<number, number>
  onChange: (next: Record<number, number>) => void
}

const BANK_ID = 'match-bank'

function DraggableChip({ item, placed }: { item: MatchItem; placed: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `match-item-${item.id}`,
    data: { itemId: item.id },
  })
  const style = { transform: transform ? CSS.Translate.toString(transform) : undefined, opacity: isDragging ? 0 : 1 }

  return (
    <button
      ref={setNodeRef}
      type="button"
      {...attributes}
      {...listeners}
      style={style}
      className={`min-w-0 max-w-full cursor-grab touch-none whitespace-normal rounded-md border px-3 py-2 text-left text-sm shadow-sm transition [overflow-wrap:anywhere] ${
        placed ? 'border-brand-navy/30 bg-white text-neutral-900' : 'border-neutral-200 bg-white text-neutral-900 hover:border-brand-navy/40'
      }`}
    >
      {item.text}
    </button>
  )
}

function DropTarget({ target, placedItem }: { target: MatchTargetOption; placedItem: MatchItem | undefined }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `match-target-${target.id}`,
    data: { targetId: target.id },
  })

  return (
    <div
      ref={setNodeRef}
      className={`grid min-h-[2.75rem] min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 rounded-md border-2 border-dashed px-3 py-2 text-sm transition ${
        isOver
          ? 'border-brand-navy bg-brand-navy/10'
          : placedItem
            ? 'border-transparent bg-neutral-50'
            : 'border-neutral-300 bg-white'
      }`}
    >
      <span className="min-w-0 whitespace-normal text-xs font-medium text-neutral-500 [overflow-wrap:anywhere]">{target.text}</span>
      <span className="text-neutral-300">→</span>
      {placedItem ? (
        <DraggableChip item={placedItem} placed />
      ) : (
        <span className="min-w-0 text-xs italic text-neutral-400 [overflow-wrap:anywhere]">Drop a match here</span>
      )}
    </div>
  )
}

function BankDroppable({ children }: { children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: BANK_ID })
  return (
    <div ref={setNodeRef} className={`space-y-2 rounded-md p-1.5 transition ${isOver ? 'bg-brand-navy/5 ring-2 ring-brand-navy/20' : ''}`}>
      {children}
    </div>
  )
}

// Left column: draggable items. Right column: fixed drop targets labeled
// with the (server-shuffled) match text. A drop is "correct" exactly when
// the placed item's id equals the target's id — both originate from the
// same Choice row, so that's the only signal needed; see QuizPlayer's
// submission logic for how that turns into `selected_choices`.
export function MatchingAnswer({ items, targets, assignments, onChange }: MatchingAnswerProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const [activeId, setActiveId] = useState<number | null>(null)

  const placedItemIds = new Set(Object.values(assignments))
  const bankItems = items.filter((item) => !placedItemIds.has(item.id))
  const activeItem = items.find((item) => item.id === activeId) ?? null

  function handleDragStart(event: DragStartEvent) {
    const itemId = event.active.data.current?.itemId
    setActiveId(typeof itemId === 'number' ? itemId : null)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null)
    const { active, over } = event
    const draggedId = active.data.current?.itemId
    if (!over || typeof draggedId !== 'number') return

    const next = { ...assignments }
    for (const key of Object.keys(next)) {
      if (next[Number(key)] === draggedId) delete next[Number(key)]
    }
    const targetId = over.data.current?.targetId
    if (over.id !== BANK_ID && typeof targetId === 'number') {
      next[targetId] = draggedId
    }
    onChange(next)
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="grid min-w-0 grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="min-w-0">
          <p className="mb-2 text-xs font-medium text-neutral-500">Items</p>
          <BankDroppable>
            {bankItems.length === 0 ? (
              <p className="rounded-md border border-dashed border-neutral-200 px-3 py-4 text-center text-xs text-neutral-400">
                All items placed
              </p>
            ) : (
              bankItems.map((item) => <DraggableChip key={item.id} item={item} placed={false} />)
            )}
          </BankDroppable>
        </div>
        <div className="min-w-0">
          <p className="mb-2 text-xs font-medium text-neutral-500">Match to</p>
          <div className="min-w-0 space-y-2">
            {targets.map((target) => (
              <DropTarget
                key={target.id}
                target={target}
                placedItem={items.find((item) => item.id === assignments[target.id])}
              />
            ))}
          </div>
        </div>
      </div>
      <DragOverlay>
        {activeItem ? (
          <div className="max-w-[min(24rem,80vw)] whitespace-normal rounded-md border border-brand-navy bg-white px-3 py-2 text-sm shadow-lg [overflow-wrap:anywhere]">{activeItem.text}</div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
