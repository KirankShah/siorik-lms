import { useEffect, useRef, useState } from 'react'
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Plus } from 'lucide-react'
import { deleteLesson, deleteModule, moveLesson, reorderLessons, reorderModules, updateModule } from '../../lib/coursesApi'
import type { CourseDetail, Lesson, Module } from '../../types/courses'
import { LessonForm } from './LessonForm'

type DragItemData =
  | { type: 'module'; moduleId: number }
  | { type: 'lesson'; lessonId: number; moduleId: number }
  | { type: 'module-container'; moduleId: number }

function moduleDndId(id: number) {
  return `module:${id}`
}
function moduleContainerDndId(id: number) {
  return `module-container:${id}`
}
function lessonDndId(id: number) {
  return `lesson:${id}`
}

function findModuleOfLesson(modules: Module[], lessonId: number): number | undefined {
  return modules.find((m) => m.lessons.some((l) => l.id === lessonId))?.id
}

function arraysEqual(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index])
}

interface CurriculumBoardProps {
  course: CourseDetail
  onChanged: () => void
}

export function CurriculumBoard({ course, onChanged }: CurriculumBoardProps) {
  const [modules, setModules] = useState<Module[]>(course.modules)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [activeType, setActiveType] = useState<'module' | 'lesson' | null>(null)
  const [overModuleId, setOverModuleId] = useState<number | null>(null)
  const [dragOriginModuleId, setDragOriginModuleId] = useState<number | null>(null)
  const [editingLessonId, setEditingLessonId] = useState<number | null>(null)
  const [addingLessonAt, setAddingLessonAt] = useState<{ moduleId: number; index: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const dragSnapshotRef = useRef<Module[] | null>(null)

  // Local state mirrors the course prop so drag gestures can move items around
  // live; re-sync whenever fresh data arrives, but never mid-drag (that would
  // yank the list out from under the user's cursor).
  useEffect(() => {
    if (activeId === null) setModules(course.modules)
  }, [course.modules, activeId])

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  function handleDragStart(event: DragStartEvent) {
    const data = event.active.data.current as DragItemData | undefined
    dragSnapshotRef.current = modules
    setActiveId(String(event.active.id))
    if (data?.type === 'module') {
      setActiveType('module')
    } else if (data?.type === 'lesson') {
      setActiveType('lesson')
      setDragOriginModuleId(findModuleOfLesson(modules, data.lessonId) ?? null)
    }
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event
    const activeData = active.data.current as DragItemData | undefined
    if (!over || activeData?.type !== 'lesson') return

    const overData = over.data.current as DragItemData | undefined
    const activeContainerId = findModuleOfLesson(modules, activeData.lessonId)
    const overContainerId =
      overData?.type === 'lesson'
        ? findModuleOfLesson(modules, overData.lessonId)
        : overData?.type === 'module-container'
          ? overData.moduleId
          : null

    if (activeContainerId == null || overContainerId == null) return
    setOverModuleId(overContainerId)

    const sourceMod = modules.find((m) => m.id === activeContainerId)
    const destMod = modules.find((m) => m.id === overContainerId)
    if (!sourceMod || !destMod) return
    const activeIndex = sourceMod.lessons.findIndex((l) => l.id === activeData.lessonId)
    if (activeIndex === -1) return

    if (activeContainerId === overContainerId) {
      if (overData?.type !== 'lesson') return
      const overIndex = destMod.lessons.findIndex((l) => l.id === overData.lessonId)
      if (overIndex === -1 || activeIndex === overIndex) return
      const reordered = arrayMove(destMod.lessons, activeIndex, overIndex)
      setModules(modules.map((m) => (m.id === destMod.id ? { ...m, lessons: reordered } : m)))
      return
    }

    const lesson = sourceMod.lessons[activeIndex]
    const newSourceLessons = sourceMod.lessons.filter((l) => l.id !== activeData.lessonId)
    let insertIndex = destMod.lessons.length
    if (overData?.type === 'lesson') {
      const overIdx = destMod.lessons.findIndex((l) => l.id === overData.lessonId)
      insertIndex = overIdx === -1 ? destMod.lessons.length : overIdx
    }
    const newDestLessons = [...destMod.lessons]
    newDestLessons.splice(insertIndex, 0, lesson)

    setModules(
      modules.map((m) => {
        if (m.id === sourceMod.id) return { ...m, lessons: newSourceLessons }
        if (m.id === destMod.id) return { ...m, lessons: newDestLessons }
        return m
      }),
    )
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    const activeData = active.data.current as DragItemData | undefined
    const snapshot = dragSnapshotRef.current
    setActiveId(null)
    setActiveType(null)
    setOverModuleId(null)
    setDragOriginModuleId(null)

    if (activeData?.type === 'module') {
      if (!over) {
        if (snapshot) setModules(snapshot)
        return
      }
      const overData = over.data.current as DragItemData | undefined
      if (overData?.type !== 'module') return
      const oldIndex = modules.findIndex((m) => m.id === activeData.moduleId)
      const newIndex = modules.findIndex((m) => m.id === overData.moduleId)
      if (oldIndex === -1 || newIndex === -1 || oldIndex === newIndex) return
      const reordered = arrayMove(modules, oldIndex, newIndex)
      setModules(reordered)
      try {
        await reorderModules(course.id, reordered.map((m) => m.id))
        onChanged()
      } catch {
        setError('Could not save the new module order.')
        setModules(snapshot ?? modules)
      }
      return
    }

    if (activeData?.type === 'lesson') {
      if (!over) {
        if (snapshot) setModules(snapshot)
        return
      }
      const lessonId = activeData.lessonId
      const originalModuleId = snapshot ? findModuleOfLesson(snapshot, lessonId) : undefined
      const currentModuleId = findModuleOfLesson(modules, lessonId)
      if (currentModuleId == null || originalModuleId == null) return

      const destMod = modules.find((m) => m.id === currentModuleId)
      if (!destMod) return
      const newLessonIds = destMod.lessons.map((l) => l.id)

      if (currentModuleId === originalModuleId) {
        const originalLessonIds = snapshot?.find((m) => m.id === originalModuleId)?.lessons.map((l) => l.id) ?? []
        if (arraysEqual(originalLessonIds, newLessonIds)) return
        try {
          await reorderLessons(currentModuleId, newLessonIds)
          onChanged()
        } catch {
          setError('Could not save the new lesson order.')
          setModules(snapshot ?? modules)
        }
      } else {
        try {
          await moveLesson(lessonId, currentModuleId, newLessonIds)
          onChanged()
        } catch {
          setError('Could not move this lesson to the new module.')
          setModules(snapshot ?? modules)
        }
      }
    }
  }

  async function handleDeleteModule(module: Module) {
    if (!window.confirm(`Delete module "${module.title}" and all its lessons?`)) return
    try {
      await deleteModule(module.id)
      onChanged()
    } catch {
      setError('Could not delete module.')
    }
  }

  async function handleDeleteLesson(lesson: Lesson) {
    if (!window.confirm(`Delete lesson "${lesson.title}"?`)) return
    try {
      await deleteLesson(lesson.id)
      onChanged()
    } catch {
      setError('Could not delete lesson.')
    }
  }

  async function handleLessonInserted(moduleId: number, index: number, createdLessonId?: number) {
    setAddingLessonAt(null)
    if (createdLessonId == null) {
      onChanged()
      return
    }
    const mod = modules.find((m) => m.id === moduleId)
    const existingIds = mod ? mod.lessons.map((l) => l.id) : []
    const newOrderIds = [...existingIds]
    newOrderIds.splice(index, 0, createdLessonId)
    try {
      await reorderLessons(moduleId, newOrderIds)
    } catch {
      setError('Lesson was added but could not be positioned — drag it into place.')
    }
    onChanged()
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-xs text-red-600">{error}</p>}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={(e) => void handleDragEnd(e)}
      >
        <SortableContext items={modules.map((m) => moduleDndId(m.id))} strategy={verticalListSortingStrategy}>
          <div className="space-y-4">
            {modules.map((module) => (
              <SortableModuleRow
                key={module.id}
                module={module}
                activeType={activeType}
                overModuleId={overModuleId}
                dragOriginModuleId={dragOriginModuleId}
                isDragActive={activeId !== null}
                editingLessonId={editingLessonId}
                addingLessonAt={addingLessonAt}
                onDeleteModule={() => handleDeleteModule(module)}
                onEditLesson={setEditingLessonId}
                onDeleteLesson={handleDeleteLesson}
                onOpenInsert={(index) => setAddingLessonAt({ moduleId: module.id, index })}
                onCancelInsert={() => setAddingLessonAt(null)}
                onCancelEditLesson={() => setEditingLessonId(null)}
                onLessonSaved={() => {
                  setEditingLessonId(null)
                  onChanged()
                }}
                onLessonInserted={(index, createdLessonId) => handleLessonInserted(module.id, index, createdLessonId)}
                onChanged={onChanged}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  )
}

interface SortableModuleRowProps {
  module: Module
  activeType: 'module' | 'lesson' | null
  overModuleId: number | null
  dragOriginModuleId: number | null
  isDragActive: boolean
  editingLessonId: number | null
  addingLessonAt: { moduleId: number; index: number } | null
  onDeleteModule: () => void
  onEditLesson: (lessonId: number) => void
  onDeleteLesson: (lesson: Lesson) => void
  onOpenInsert: (index: number) => void
  onCancelInsert: () => void
  onCancelEditLesson: () => void
  onLessonSaved: () => void
  onLessonInserted: (index: number, createdLessonId?: number) => void
  onChanged: () => void
}

function SortableModuleRow({
  module,
  activeType,
  overModuleId,
  dragOriginModuleId,
  isDragActive,
  editingLessonId,
  addingLessonAt,
  onDeleteModule,
  onEditLesson,
  onDeleteLesson,
  onOpenInsert,
  onCancelInsert,
  onCancelEditLesson,
  onLessonSaved,
  onLessonInserted,
  onChanged,
}: SortableModuleRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: moduleDndId(module.id),
    data: { type: 'module', moduleId: module.id },
  })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  const { setNodeRef: setDroppableRef } = useDroppable({
    id: moduleContainerDndId(module.id),
    data: { type: 'module-container', moduleId: module.id },
  })

  const [isEditingModule, setIsEditingModule] = useState(false)
  const [title, setTitle] = useState(module.title)
  const [moduleError, setModuleError] = useState<string | null>(null)

  async function handleSaveModule() {
    try {
      await updateModule(module.id, { title })
      setIsEditingModule(false)
      onChanged()
    } catch {
      setModuleError('Could not update module.')
    }
  }

  const isDropTarget = activeType === 'lesson' && overModuleId === module.id
  const isCrossModuleTarget = isDropTarget && dragOriginModuleId !== null && dragOriginModuleId !== module.id
  const isSameModuleTarget = isDropTarget && dragOriginModuleId === module.id

  const containerClasses = [
    'mt-3 min-h-[2.5rem] space-y-1 rounded-md border-2 p-1 transition-colors',
    isCrossModuleTarget && 'border-dashed border-amber-500 bg-amber-50',
    isSameModuleTarget && 'border-dashed border-brand-navy/40 bg-brand-navy/5',
    !isDropTarget && 'border-transparent',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div ref={setNodeRef} style={style} className="rounded-lg border border-neutral-200 p-4">
      <div className="flex items-center justify-between">
        <div className="flex flex-1 items-center gap-2">
          <button
            type="button"
            {...attributes}
            {...listeners}
            className="shrink-0 cursor-grab touch-none text-neutral-300 hover:text-neutral-500"
            aria-label="Drag to reorder module"
          >
            <GripVertical className="h-4 w-4" />
          </button>
          {isEditingModule ? (
            <div className="flex flex-1 items-center gap-2">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="rounded border border-neutral-300 px-2 py-1 text-sm"
              />
              <button onClick={handleSaveModule} className="text-sm font-medium text-brand-navy">
                Save
              </button>
              <button onClick={() => setIsEditingModule(false)} className="text-sm text-neutral-500">
                Cancel
              </button>
            </div>
          ) : (
            <h3 className="text-sm font-semibold text-neutral-900">
              {module.order}. {module.title}
            </h3>
          )}
        </div>
        {!isEditingModule && (
          <div className="flex gap-3 text-sm">
            <button type="button" onClick={() => setIsEditingModule(true)} className="text-brand-navy hover:underline">
              Edit
            </button>
            <button type="button" onClick={onDeleteModule} className="text-red-600 hover:underline">
              Delete
            </button>
          </div>
        )}
      </div>

      {moduleError && <p className="mt-2 text-xs text-red-600">{moduleError}</p>}
      {isCrossModuleTarget && (
        <p className="mt-2 text-xs font-medium text-amber-700">Drop to move this lesson into &ldquo;{module.title}&rdquo;</p>
      )}

      <div ref={setDroppableRef} className={containerClasses}>
        <SortableContext items={module.lessons.map((l) => lessonDndId(l.id))} strategy={verticalListSortingStrategy}>
          {module.lessons.map((lesson, idx) => (
            <div key={lesson.id}>
              {addingLessonAt?.moduleId === module.id && addingLessonAt.index === idx ? (
                <div className="my-2">
                  <LessonForm
                    moduleId={module.id}
                    nextOrder={module.lessons.length + 1}
                    onSaved={(createdId) => onLessonInserted(idx, createdId)}
                    onCancel={onCancelInsert}
                  />
                </div>
              ) : (
                !isDragActive && <InsertLessonGap onClick={() => onOpenInsert(idx)} />
              )}
              {editingLessonId === lesson.id ? (
                <LessonForm moduleId={module.id} lesson={lesson} onSaved={onLessonSaved} onCancel={onCancelEditLesson} />
              ) : (
                <SortableLessonRow
                  lesson={lesson}
                  moduleId={module.id}
                  onEdit={() => onEditLesson(lesson.id)}
                  onDelete={() => onDeleteLesson(lesson)}
                />
              )}
            </div>
          ))}
        </SortableContext>
        {module.lessons.length === 0 && (
          <p className="rounded-md border border-dashed border-neutral-200 px-3 py-4 text-center text-xs text-neutral-400">
            No lessons yet — drop a lesson here, or add one below.
          </p>
        )}
      </div>

      {addingLessonAt?.moduleId === module.id && addingLessonAt.index === module.lessons.length ? (
        <div className="mt-3">
          <LessonForm
            moduleId={module.id}
            nextOrder={module.lessons.length + 1}
            onSaved={(createdId) => onLessonInserted(module.lessons.length, createdId)}
            onCancel={onCancelInsert}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => onOpenInsert(module.lessons.length)}
          className="mt-3 text-sm font-medium text-brand-navy hover:underline"
        >
          + Add lesson
        </button>
      )}
    </div>
  )
}

interface SortableLessonRowProps {
  lesson: Lesson
  moduleId: number
  onEdit: () => void
  onDelete: () => void
}

function SortableLessonRow({ lesson, moduleId, onEdit, onDelete }: SortableLessonRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: lessonDndId(lesson.id),
    data: { type: 'lesson', lessonId: lesson.id, moduleId },
  })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center justify-between gap-2 rounded-md border border-neutral-100 bg-white px-3 py-2 text-sm"
    >
      <div className="flex min-w-0 items-center gap-2">
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="shrink-0 cursor-grab touch-none text-neutral-300 hover:text-neutral-500"
          aria-label="Drag to reorder lesson"
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <span className="truncate">
          {lesson.order}. {lesson.title} <span className="text-xs text-neutral-400">({lesson.lesson_type})</span>
          <span className="ml-2 text-xs text-neutral-400">
            {lesson.slides.length} slide{lesson.slides.length === 1 ? '' : 's'}
          </span>
        </span>
      </div>
      <div className="flex shrink-0 gap-3">
        <button type="button" onClick={onEdit} className="text-brand-navy hover:underline">
          Edit
        </button>
        <button type="button" onClick={onDelete} className="text-red-600 hover:underline">
          Delete
        </button>
      </div>
    </div>
  )
}

function InsertLessonGap({ onClick }: { onClick: () => void }) {
  return (
    <div className="group/gap relative h-2 transition-all hover:h-7">
      <button
        type="button"
        onClick={onClick}
        className="absolute inset-x-0 top-1/2 hidden -translate-y-1/2 items-center justify-center gap-1 rounded-full border border-dashed border-brand-navy/40 bg-white px-3 py-0.5 text-xs font-medium text-brand-navy shadow-sm hover:border-brand-navy group-hover/gap:flex"
      >
        <Plus className="h-3 w-3" /> Add lesson here
      </button>
    </div>
  )
}
