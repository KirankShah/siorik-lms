import { useState } from 'react'
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
import { createPage, deletePage, reorderPages, updatePage, fetchPage } from '../../lib/pagesApi'
import { copyPageToClipboard, hasPageClipboard, readPageClipboard } from '../../lib/pageClipboard'
import type { CourseDetail, Lesson, Module, PageSummary, PageType } from '../../types/courses'

const PAGE_TYPE_ICON: Record<PageType, string> = {
  CONTENT: '📄',
  QUIZ: '❓',
  ASSIGNMENT: '📋',
}

interface LessonTreeProps {
  course: CourseDetail
  selectedPageId: number | null
  onSelectPage: (id: number | null) => void
  onChanged: () => void
}

export function LessonTree({ course, selectedPageId, onSelectPage, onChanged }: LessonTreeProps) {
  return (
    <nav className="space-y-3">
      {course.modules.map((module) => (
        <ModuleNode
          key={module.id}
          module={module}
          selectedPageId={selectedPageId}
          onSelectPage={onSelectPage}
          onChanged={onChanged}
        />
      ))}
      {course.modules.length === 0 && <p className="text-xs text-slate-400">No modules yet.</p>}
    </nav>
  )
}

function ModuleNode({
  module,
  selectedPageId,
  onSelectPage,
  onChanged,
}: {
  module: Module
  selectedPageId: number | null
  onSelectPage: (id: number | null) => void
  onChanged: () => void
}) {
  return (
    <div>
      <p className="px-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">
        {module.order}. {module.title}
      </p>
      <div className="mt-1 space-y-2">
        {module.lessons.map((lesson) => (
          <LessonNode key={lesson.id} lesson={lesson} selectedPageId={selectedPageId} onSelectPage={onSelectPage} onChanged={onChanged} />
        ))}
      </div>
    </div>
  )
}

function LessonNode({
  lesson,
  selectedPageId,
  onSelectPage,
  onChanged,
}: {
  lesson: Lesson
  selectedPageId: number | null
  onSelectPage: (id: number | null) => void
  onChanged: () => void
}) {
  const [isAdding, setIsAdding] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newType, setNewType] = useState<PageType>('CONTENT')
  const [error, setError] = useState<string | null>(null)
  const [orderedPages, setOrderedPages] = useState<PageSummary[] | null>(null)

  // While a drag is settling with the server, trust local optimistic order
  // over the (possibly stale) prop from the last course fetch.
  const pages = orderedPages ?? lesson.pages

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  async function handleAddPage() {
    if (!newTitle.trim()) return
    try {
      const created = await createPage({
        lesson: lesson.id,
        title: newTitle,
        page_type: newType,
        order: pages.length + 1,
      })
      setNewTitle('')
      setIsAdding(false)
      onChanged()
      onSelectPage(created.id)
    } catch {
      setError('Could not create page.')
    }
  }

  async function handlePaste() {
    const clipboard = readPageClipboard()
    if (!clipboard) return
    try {
      const created = await createPage({
        lesson: lesson.id,
        title: `${clipboard.title} (copy)`,
        page_type: clipboard.page_type,
        content_json: clipboard.content_json,
        estimated_minutes: clipboard.estimated_minutes,
        order: pages.length + 1,
      })
      onChanged()
      onSelectPage(created.id)
    } catch {
      setError('Could not paste page here.')
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = pages.findIndex((p) => p.id === active.id)
    const newIndex = pages.findIndex((p) => p.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return

    const reordered = arrayMove(pages, oldIndex, newIndex)
    setOrderedPages(reordered)

    try {
      const persisted = await reorderPages(
        lesson.id,
        reordered.map((p) => p.id),
      )
      setOrderedPages(persisted)
    } catch {
      setError('Could not save the new page order.')
      setOrderedPages(lesson.pages)
    }
  }

  return (
    <div className="rounded-md border border-slate-100 pl-2">
      <p className="py-1 text-xs font-medium text-slate-600">
        {lesson.order}. {lesson.title}
      </p>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleDragEnd(e)}>
        <SortableContext items={pages.map((p) => p.id)} strategy={verticalListSortingStrategy}>
          <ul className="space-y-0.5">
            {pages.map((page) => (
              <PageTreeItem
                key={page.id}
                page={page}
                nextOrder={pages.length + 1}
                isSelected={page.id === selectedPageId}
                onSelect={() => onSelectPage(page.id)}
                onSelectId={onSelectPage}
                onChanged={onChanged}
                onError={setError}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>

      {error && <p className="py-1 text-xs text-red-600">{error}</p>}

      {isAdding ? (
        <div className="flex items-center gap-1 py-1 pr-1">
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Page title"
            autoFocus
            className="min-w-0 flex-1 rounded border border-slate-300 px-1.5 py-0.5 text-xs"
          />
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as PageType)}
            className="rounded border border-slate-300 px-1 py-0.5 text-xs"
          >
            <option value="CONTENT">Content</option>
            <option value="QUIZ">Quiz</option>
            <option value="ASSIGNMENT">Assignment</option>
          </select>
          <button type="button" onClick={() => void handleAddPage()} className="text-xs font-medium text-emerald-700">
            Add
          </button>
          <button type="button" onClick={() => setIsAdding(false)} className="text-xs text-slate-500">
            ✕
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2 py-1 pr-1">
          <button type="button" onClick={() => setIsAdding(true)} className="text-xs font-medium text-slate-500 hover:text-slate-900">
            + Add page
          </button>
          {hasPageClipboard() && (
            <button type="button" onClick={() => void handlePaste()} className="text-xs font-medium text-slate-500 hover:text-slate-900">
              Paste page
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function PageTreeItem({
  page,
  nextOrder,
  isSelected,
  onSelect,
  onSelectId,
  onChanged,
  onError,
}: {
  page: PageSummary
  nextOrder: number
  isSelected: boolean
  onSelect: () => void
  onSelectId: (id: number | null) => void
  onChanged: () => void
  onError: (message: string | null) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: page.id })
  const [isEditing, setIsEditing] = useState(false)
  const [title, setTitle] = useState(page.title)

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  async function commitRename() {
    setIsEditing(false)
    if (!title.trim() || title === page.title) {
      setTitle(page.title)
      return
    }
    try {
      await updatePage(page.id, { title })
      onChanged()
    } catch {
      onError('Could not rename page.')
      setTitle(page.title)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete page "${page.title}"? This cannot be undone.`)) return
    try {
      await deletePage(page.id)
      onChanged()
      if (isSelected) onSelectId(null)
    } catch {
      onError('Could not delete page.')
    }
  }

  async function handleDuplicate() {
    try {
      const full = await fetchPage(page.id)
      const created = await createPage({
        lesson: full.lesson,
        title: `${full.title} (copy)`,
        page_type: full.page_type,
        content_json: full.content_json,
        estimated_minutes: full.estimated_minutes,
        order: nextOrder,
      })
      onChanged()
      onSelectId(created.id)
    } catch {
      onError('Could not duplicate page.')
    }
  }

  async function handleCopy() {
    try {
      const full = await fetchPage(page.id)
      copyPageToClipboard({
        title: full.title,
        page_type: full.page_type,
        content_json: full.content_json,
        estimated_minutes: full.estimated_minutes,
      })
    } catch {
      onError('Could not copy page.')
    }
  }

  return (
    <li ref={setNodeRef} style={style}>
      <div
        className={`group flex items-center gap-1 rounded px-1 py-1 text-xs ${
          isSelected ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
        }`}
      >
        <button
          type="button"
          {...attributes}
          {...listeners}
          className={`shrink-0 cursor-grab touch-none px-0.5 ${isSelected ? 'text-white/60' : 'text-slate-300'}`}
          aria-label="Drag to reorder"
        >
          ⠿
        </button>
        <span className="shrink-0">{PAGE_TYPE_ICON[page.page_type]}</span>

        {isEditing ? (
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => void commitRename()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void commitRename()
              if (e.key === 'Escape') {
                setTitle(page.title)
                setIsEditing(false)
              }
            }}
            className="min-w-0 flex-1 rounded border border-slate-300 px-1 py-0.5 text-xs text-slate-900"
          />
        ) : (
          <button type="button" onClick={onSelect} onDoubleClick={() => setIsEditing(true)} className="min-w-0 flex-1 truncate text-left">
            {page.title}
          </button>
        )}

        <div className={`flex shrink-0 gap-1 opacity-0 group-hover:opacity-100 ${isSelected ? 'text-white/80' : 'text-slate-400'}`}>
          <button type="button" onClick={() => setIsEditing(true)} title="Rename" className="hover:text-inherit">
            ✎
          </button>
          <button type="button" onClick={() => void handleCopy()} title="Copy" className="hover:text-inherit">
            ⧉
          </button>
          <button type="button" onClick={() => void handleDuplicate()} title="Duplicate" className="hover:text-inherit">
            ⎘
          </button>
          <button type="button" onClick={() => void handleDelete()} title="Delete" className="hover:text-red-400">
            ✕
          </button>
        </div>
      </div>
    </li>
  )
}
