import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
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
import { injectBlankMarkup } from '../lib/fillBlankMarkup'

export interface WordBankTokenOption {
  id: number
  text: string
}

interface WordBankAnswerProps {
  questionHtml: string
  tokens: WordBankTokenOption[]
  // blankIndex -> tokenId
  placements: Record<number, number>
  onChange: (next: Record<number, number>) => void
}

const BANK_ID = 'word-bank-tray'

function DraggableToken({ token }: { token: WordBankTokenOption }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: token.id })
  const style = { transform: transform ? CSS.Translate.toString(transform) : undefined, opacity: isDragging ? 0 : 1 }
  return (
    <button
      ref={setNodeRef}
      type="button"
      {...attributes}
      {...listeners}
      style={style}
      className="cursor-grab touch-none rounded-md border border-neutral-200 bg-white px-3 py-1.5 text-sm shadow-sm transition hover:border-brand-navy/40"
    >
      {token.text}
    </button>
  )
}

function BlankDropTarget({
  blankIndex,
  placedToken,
}: {
  blankIndex: number
  placedToken: WordBankTokenOption | undefined
}) {
  const { setNodeRef, isOver } = useDroppable({ id: blankIndex })
  return (
    <span
      ref={setNodeRef}
      className={`mx-1 inline-flex min-w-[5rem] items-center justify-center rounded border-2 border-dashed px-2 py-0.5 align-middle text-sm transition ${
        isOver ? 'border-brand-navy bg-brand-navy/10' : placedToken ? 'border-transparent bg-brand-navy/5' : 'border-neutral-300'
      }`}
    >
      {placedToken ? <DraggableToken token={placedToken} /> : <span className="text-neutral-300">___</span>}
    </span>
  )
}

function BankDroppable({ children }: { children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: BANK_ID })
  return (
    <div
      ref={setNodeRef}
      className={`mt-4 flex min-h-[3.5rem] flex-wrap gap-2 rounded-md border-2 border-dashed p-3 transition ${
        isOver ? 'border-brand-navy bg-brand-navy/5' : 'border-neutral-200 bg-neutral-50'
      }`}
    >
      {children}
    </div>
  )
}

// Same inline-portal technique as FillBlankTextAnswer, but each blank is a
// dnd-kit drop target instead of a text box, fed by a shuffled bank of
// draggable tokens below the question.
export function WordBankAnswer({ questionHtml, tokens, placements, onChange }: WordBankAnswerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [targets, setTargets] = useState<Record<number, HTMLElement>>({})
  const [activeId, setActiveId] = useState<number | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const injectedHtml = useMemo(() => injectBlankMarkup(questionHtml), [questionHtml])

  useLayoutEffect(() => {
    if (!containerRef.current) return
    const found: Record<number, HTMLElement> = {}
    containerRef.current.querySelectorAll('[data-blank-index]').forEach((el) => {
      found[Number(el.getAttribute('data-blank-index'))] = el as HTMLElement
    })
    setTargets(found)
  }, [injectedHtml])

  const placedTokenIds = new Set(Object.values(placements))
  const unplaced = tokens.filter((token) => !placedTokenIds.has(token.id))
  const activeToken = tokens.find((token) => token.id === activeId) ?? null

  function handleDragStart(event: DragStartEvent) {
    setActiveId(typeof event.active.id === 'number' ? event.active.id : null)
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null)
    const { active, over } = event
    if (!over || typeof active.id !== 'number') return
    const draggedId = active.id

    const next = { ...placements }
    for (const key of Object.keys(next)) {
      if (next[Number(key)] === draggedId) delete next[Number(key)]
    }
    if (over.id !== BANK_ID && typeof over.id === 'number') {
      next[over.id] = draggedId
    }
    onChange(next)
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div
        ref={containerRef}
        className="text-sm leading-relaxed text-neutral-900"
        dangerouslySetInnerHTML={{ __html: injectedHtml }}
      />
      {Object.entries(targets).map(([indexStr, el]) => {
        const index = Number(indexStr)
        const placedToken = tokens.find((token) => token.id === placements[index])
        return createPortal(<BlankDropTarget blankIndex={index} placedToken={placedToken} />, el, `blank-${index}`)
      })}
      <div>
        <p className="mb-1 text-xs font-medium text-neutral-500">Word bank</p>
        <BankDroppable>
          {unplaced.length === 0 ? (
            <p className="text-xs italic text-neutral-400">All tokens placed</p>
          ) : (
            unplaced.map((token) => <DraggableToken key={token.id} token={token} />)
          )}
        </BankDroppable>
      </div>
      <DragOverlay>
        {activeToken ? (
          <div className="rounded-md border border-brand-navy bg-white px-3 py-1.5 text-sm shadow-lg">{activeToken.text}</div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
