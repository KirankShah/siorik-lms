import { useState } from 'react'
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

export interface CategorizeItemOption {
  id: number
  text: string
  image: string | null
}

export interface CategorizeBucketOption {
  id: number
  label: string
}

interface CategorizeAnswerProps {
  items: CategorizeItemOption[]
  buckets: CategorizeBucketOption[]
  // itemId -> bucketId the learner has placed it in; absent = unplaced.
  placements: Record<number, number>
  onChange: (next: Record<number, number>) => void
}

const TRAY_ID = 'categorize-tray'

function DraggableItemChip({ item }: { item: CategorizeItemOption }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: item.id })
  const style = { transform: transform ? CSS.Translate.toString(transform) : undefined, opacity: isDragging ? 0 : 1 }

  return (
    <button
      ref={setNodeRef}
      type="button"
      {...attributes}
      {...listeners}
      style={style}
      className="flex cursor-grab touch-none items-center gap-2 rounded-md border border-neutral-200 bg-white px-3 py-2 text-left text-sm shadow-sm transition hover:border-brand-navy/40"
    >
      {item.image && <img src={item.image} alt="" className="h-6 w-6 shrink-0 rounded object-cover" />}
      {item.text}
    </button>
  )
}

function TrayDroppable({ isEmpty, children }: { isEmpty: boolean; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: TRAY_ID })
  return (
    <div
      ref={setNodeRef}
      className={`flex min-h-[3.5rem] flex-wrap gap-2 rounded-md border-2 border-dashed p-3 transition ${
        isOver ? 'border-brand-navy bg-brand-navy/5' : isEmpty ? 'border-neutral-200 bg-neutral-50' : 'border-transparent bg-neutral-50'
      }`}
    >
      {children}
    </div>
  )
}

function BucketDroppable({ bucket, items }: { bucket: CategorizeBucketOption; items: CategorizeItemOption[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: bucket.id })
  return (
    <div
      ref={setNodeRef}
      className={`min-h-[9rem] min-w-[200px] flex-1 rounded-md border-2 border-dashed p-3 transition ${
        isOver ? 'border-brand-navy bg-brand-navy/10' : 'border-neutral-300 bg-white'
      }`}
    >
      <p className="mb-2 text-xs font-semibold text-neutral-600">{bucket.label}</p>
      <div className="space-y-2">
        {items.length === 0 ? (
          <p className="text-xs italic text-neutral-400">Drop items here</p>
        ) : (
          items.map((item) => <DraggableItemChip key={item.id} item={item} />)
        )}
      </div>
    </div>
  )
}

// Items shuffle into a tray above; the learner drags each one down into the
// bucket they believe is correct. A bucket can hold any number of items —
// unlike MatchingAnswer's strict 1:1 pairing — so drop targets are the
// buckets themselves rather than one slot per item.
export function CategorizeAnswer({ items, buckets, placements, onChange }: CategorizeAnswerProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const [activeId, setActiveId] = useState<number | null>(null)

  const unplaced = items.filter((item) => placements[item.id] === undefined)
  const activeItem = items.find((item) => item.id === activeId) ?? null

  function handleDragStart(event: DragStartEvent) {
    setActiveId(typeof event.active.id === 'number' ? event.active.id : null)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null)
    const { active, over } = event
    if (!over || typeof active.id !== 'number') return

    const next = { ...placements }
    if (over.id === TRAY_ID) {
      delete next[active.id]
    } else if (typeof over.id === 'number') {
      next[active.id] = over.id
    }
    onChange(next)
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div>
        <p className="mb-2 text-xs font-medium text-neutral-500">Items</p>
        <TrayDroppable isEmpty={unplaced.length === 0}>
          {unplaced.length === 0 ? (
            <p className="text-xs italic text-neutral-400">All items placed</p>
          ) : (
            unplaced.map((item) => <DraggableItemChip key={item.id} item={item} />)
          )}
        </TrayDroppable>
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        {buckets.map((bucket) => (
          <BucketDroppable key={bucket.id} bucket={bucket} items={items.filter((item) => placements[item.id] === bucket.id)} />
        ))}
      </div>
      <DragOverlay>
        {activeItem ? (
          <div className="flex items-center gap-2 rounded-md border border-brand-navy bg-white px-3 py-2 text-sm shadow-lg">
            {activeItem.image && <img src={activeItem.image} alt="" className="h-6 w-6 rounded object-cover" />}
            {activeItem.text}
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
