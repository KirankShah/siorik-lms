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
import { Plus } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import { SlideCard } from '../../components/admin/SlideCard'
import { createSlide, deleteSlide, duplicateSlide, reorderSlides } from '../../lib/slidesApi'
import type { SlideSummary, SlideType } from '../../types/slides'
import type { CourseDashboardContext } from './CourseDashboardLayout'

const SLIDE_TYPE_LABEL: Record<SlideType, string> = {
  CONTENT: 'Content',
  QUIZ: 'Quiz',
  ASSIGNMENT: 'Assignment',
  SCENARIO: 'Scenario',
}

interface SortableSlideCardProps {
  slide: SlideSummary
  onDuplicate: () => void
  onDelete: () => void
  onRenamed: () => void
}

function SortableSlideCard({ slide, onDuplicate, onDelete, onRenamed }: SortableSlideCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: slide.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <div ref={setNodeRef} style={style}>
      <SlideCard
        slide={slide}
        dragHandleProps={{ ...attributes, ...listeners }}
        onDuplicate={onDuplicate}
        onDelete={onDelete}
        onRenamed={onRenamed}
      />
    </div>
  )
}

function AddSlideForm({ lessonId, nextOrder, onAdded }: { lessonId: number; nextOrder: number; onAdded: () => void }) {
  const [isOpen, setIsOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [slideType, setSlideType] = useState<SlideType>('CONTENT')
  const [error, setError] = useState<string | null>(null)

  async function handleAdd() {
    try {
      await createSlide({ lesson: lessonId, title, slide_type: slideType, order: nextOrder })
      setTitle('')
      setSlideType('CONTENT')
      setIsOpen(false)
      onAdded()
    } catch {
      setError('Could not create this slide.')
    }
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-neutral-300 px-4 py-2.5 text-sm font-medium text-neutral-600 transition hover:border-brand-navy hover:text-brand-navy"
      >
        <Plus className="h-4 w-4" />
        Add new slide
      </button>
    )
  }

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label className="block text-xs font-medium text-neutral-500">Title (optional)</label>
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500">Type</label>
          <select
            value={slideType}
            onChange={(e) => setSlideType(e.target.value as SlideType)}
            className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
          >
            {Object.entries(SLIDE_TYPE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <button type="button" onClick={handleAdd} className="text-sm font-medium text-brand-navy hover:underline">
          Add
        </button>
        <button type="button" onClick={() => setIsOpen(false)} className="text-sm text-neutral-500 hover:underline">
          Cancel
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  )
}

export function CourseSlidesTab() {
  const { course, reload } = useOutletContext<CourseDashboardContext>()
  const allLessons = course.modules.flatMap((module) => module.lessons)
  const [selectedLessonId, setSelectedLessonId] = useState<number | null>(allLessons[0]?.id ?? null)
  const [orderedSlides, setOrderedSlides] = useState<SlideSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const selectedLesson = allLessons.find((lesson) => lesson.id === selectedLessonId) ?? allLessons[0] ?? null
  const slides = orderedSlides ?? (selectedLesson ? [...selectedLesson.slides].sort((a, b) => a.order - b.order) : [])

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  function selectLesson(lessonId: number) {
    setSelectedLessonId(lessonId)
    setOrderedSlides(null)
  }

  function refreshSlides() {
    setOrderedSlides(null)
    reload()
  }

  async function handleSlideDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id || !selectedLesson) return

    const oldIndex = slides.findIndex((slide) => slide.id === active.id)
    const newIndex = slides.findIndex((slide) => slide.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return

    const reordered = arrayMove(slides, oldIndex, newIndex)
    setOrderedSlides(reordered)

    try {
      const persisted = await reorderSlides(selectedLesson.id, reordered.map((slide) => slide.id))
      setOrderedSlides(persisted)
      reload()
    } catch {
      setError('Could not save the new slide order.')
      setOrderedSlides(null)
    }
  }

  async function handleDuplicate(slide: SlideSummary) {
    try {
      await duplicateSlide(slide.id)
      refreshSlides()
    } catch {
      setError('Could not duplicate this slide.')
    }
  }

  async function handleDelete(slide: SlideSummary) {
    if (!window.confirm(`Delete "${slide.title || `Slide ${slide.order}`}"? This cannot be undone.`)) return
    try {
      await deleteSlide(slide.id)
      refreshSlides()
    } catch {
      setError('Could not delete this slide.')
    }
  }

  if (allLessons.length === 0) {
    return (
      <p className="text-sm text-neutral-500">
        No lessons yet — add one from the Settings tab, then come back here to add slides.
      </p>
    )
  }

  return (
    <div>
      <div className="max-w-xs">
        <label className="block text-xs font-medium text-neutral-500">Lesson</label>
        <select
          value={selectedLesson?.id ?? ''}
          onChange={(e) => selectLesson(Number(e.target.value))}
          className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
        >
          {course.modules.map((module) => (
            <optgroup key={module.id} label={module.title}>
              {module.lessons.map((lesson) => (
                <option key={lesson.id} value={lesson.id}>
                  {lesson.title}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {selectedLesson && (
        <div className="mt-6 space-y-4">
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleSlideDragEnd(e)}>
            <SortableContext items={slides.map((slide) => slide.id)} strategy={verticalListSortingStrategy}>
              {slides.map((slide) => (
                <SortableSlideCard
                  key={slide.id}
                  slide={slide}
                  onDuplicate={() => handleDuplicate(slide)}
                  onDelete={() => handleDelete(slide)}
                  onRenamed={refreshSlides}
                />
              ))}
            </SortableContext>
          </DndContext>

          {slides.length === 0 && <p className="text-sm text-neutral-400">No slides in this lesson yet.</p>}

          <AddSlideForm lessonId={selectedLesson.id} nextOrder={slides.length + 1} onAdded={refreshSlides} />
        </div>
      )}
    </div>
  )
}
