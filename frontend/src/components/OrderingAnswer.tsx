import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'

export interface OrderingItem {
  id: number
  text: string
}

interface OrderingAnswerProps {
  items: OrderingItem[]
  order: number[]
  onChange: (next: number[]) => void
}

function SortableOrderingItem({ item, index }: { item: OrderingItem; index: number }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 rounded-md border border-neutral-200 bg-white px-3 py-2.5 text-sm shadow-sm"
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="shrink-0 cursor-grab touch-none text-neutral-300 hover:text-neutral-500"
        aria-label="Drag to reorder"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-100 text-xs font-medium text-neutral-500">
        {index + 1}
      </span>
      <span className="text-neutral-900">{item.text}</span>
    </li>
  )
}

// A plain vertical drag-to-reorder list — the learner's answer *is* the
// resulting order, reflected live in `order` as items are dragged around.
export function OrderingAnswer({ items, order, onChange }: OrderingAnswerProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const ordered = order
    .map((id) => items.find((item) => item.id === id))
    .filter((item): item is OrderingItem => item !== undefined)

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = order.findIndex((id) => id === active.id)
    const newIndex = order.findIndex((id) => id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    onChange(arrayMove(order, oldIndex, newIndex))
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={order} strategy={verticalListSortingStrategy}>
        <ul className="space-y-2">
          {ordered.map((item, index) => (
            <SortableOrderingItem key={item.id} item={item} index={index} />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  )
}
