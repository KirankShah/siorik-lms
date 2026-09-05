import { useEffect, useState } from 'react'
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
import { Copy, GripVertical, Pencil, Plus, Trash2 } from 'lucide-react'
import { AssignmentAuthoringPanel } from './AssignmentAuthoringPanel'
import { AssignmentSummaryPreview } from './AssignmentSummaryPreview'
import { ElementFormModal } from './ElementFormModal'
import { ElementTypePicker } from './ElementTypePicker'
import { ImageWidthPicker } from './ImageWidthPicker'
import { LayoutPicker } from './LayoutPicker'
import { NarrationPanel } from './NarrationPanel'
import { TemplatePicker } from './TemplatePicker'
import { ElementPreview } from '../ElementPreview'
import { SlideElementsView } from '../SlideElementsView'
import { QuizAuthoringPanel } from './QuizAuthoringPanel'
import { QuizSummaryPreview } from './QuizSummaryPreview'
import { ScenarioAuthoringPanel } from './ScenarioAuthoringPanel'
import { ScenarioSummaryPreview } from './ScenarioSummaryPreview'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'
import { ELEMENT_TYPE_LABEL } from '../../lib/elementTypes'
import { deleteElement, fetchElements, reorderElements, updateSlide } from '../../lib/slidesApi'
import { fetchSlideTemplates } from '../../lib/slideTemplatesApi'
import type {
  ElementType,
  ImageColumnWidth,
  Layout,
  SlideElement,
  SlideSummary,
  SlideTemplate,
  SlideType,
} from '../../types/slides'

const SLIDE_TYPE_LABEL: Record<SlideType, string> = {
  CONTENT: 'Content',
  QUIZ: 'Quiz',
  ASSIGNMENT: 'Assignment',
  SCENARIO: 'Scenario',
}

interface SortableElementRowProps {
  element: SlideElement
  onEdit: () => void
  onDelete: () => void
}

function SortableElementRow({ element, onEdit, onDelete }: SortableElementRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: element.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <div ref={setNodeRef} style={style} className="flex items-start gap-2 rounded-md border border-neutral-200 p-3">
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="mt-0.5 shrink-0 cursor-grab touch-none text-neutral-300"
        aria-label="Drag to reorder element"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <div className="min-w-0 flex-1">
        <Badge>{ELEMENT_TYPE_LABEL[element.element_type]}</Badge>
        <div className="mt-1.5">
          <ElementPreview element={element} />
        </div>
      </div>
      <div className="flex shrink-0 gap-3 text-xs">
        <button type="button" onClick={onEdit} className="font-medium text-brand-navy hover:underline">
          Edit
        </button>
        <button type="button" onClick={onDelete} className="font-medium text-red-600 hover:underline">
          Delete
        </button>
      </div>
    </div>
  )
}

interface SlideCardProps {
  slide: SlideSummary
  dragHandleProps: React.HTMLAttributes<HTMLButtonElement>
  courseTemplateId: number | null
  onDuplicate: () => void
  onDelete: () => void
  onUpdated: () => void
}

export function SlideCard({ slide, dragHandleProps, courseTemplateId, onDuplicate, onDelete, onUpdated }: SlideCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [elements, setElements] = useState<SlideElement[] | null>(null)
  const [templates, setTemplates] = useState<SlideTemplate[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isRenaming, setIsRenaming] = useState(false)
  const [titleDraft, setTitleDraft] = useState(slide.title)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pendingType, setPendingType] = useState<ElementType | null>(null)
  const [editingElement, setEditingElement] = useState<SlideElement | null>(null)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  useEffect(() => {
    if (slide.slide_type !== 'CONTENT') return
    fetchSlideTemplates().then(setTemplates).catch(() => {})
  }, [slide.slide_type])

  const effectiveTemplateId = slide.template_override ?? courseTemplateId
  const effectiveTemplate = effectiveTemplateId === null ? null : (templates.find((t) => t.id === effectiveTemplateId) ?? null)

  function loadElements() {
    if (slide.slide_type !== 'CONTENT') return
    fetchElements(slide.id)
      .then(setElements)
      .catch(() => setError('Could not load this slide’s content.'))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadElements, [slide.id, slide.slide_type])

  async function commitRename() {
    setIsRenaming(false)
    if (titleDraft === slide.title) return
    try {
      await updateSlide(slide.id, { title: titleDraft })
      onUpdated()
    } catch {
      setError('Could not rename this slide.')
      setTitleDraft(slide.title)
    }
  }

  async function handleLayoutChange(layout: Layout) {
    if (layout === slide.layout) return
    try {
      await updateSlide(slide.id, { layout })
      onUpdated()
    } catch {
      setError('Could not update this slide’s layout.')
    }
  }

  async function handleImageColumnWidthChange(imageColumnWidth: ImageColumnWidth) {
    if (imageColumnWidth === slide.image_column_width) return
    try {
      await updateSlide(slide.id, { image_column_width: imageColumnWidth })
      onUpdated()
    } catch {
      setError('Could not update this slide’s image width.')
    }
  }

  async function handleTemplateOverrideChange(templateOverride: number | null) {
    if (templateOverride === slide.template_override) return
    try {
      await updateSlide(slide.id, { template_override: templateOverride })
      onUpdated()
    } catch {
      setError('Could not update this slide’s template.')
    }
  }

  async function handleDeleteElement(element: SlideElement) {
    if (!window.confirm('Delete this element? This cannot be undone.')) return
    try {
      await deleteElement(element.id)
      loadElements()
    } catch {
      setError('Could not delete this element.')
    }
  }

  async function handleElementDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id || !elements) return

    const oldIndex = elements.findIndex((el) => el.id === active.id)
    const newIndex = elements.findIndex((el) => el.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return

    const reordered = arrayMove(elements, oldIndex, newIndex)
    setElements(reordered)

    try {
      const persisted = await reorderElements(
        slide.id,
        reordered.map((el) => el.id),
      )
      setElements(persisted)
    } catch {
      setError('Could not save the new element order.')
      loadElements()
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <button
            type="button"
            {...dragHandleProps}
            className="shrink-0 cursor-grab touch-none text-neutral-300"
            aria-label="Drag to reorder slide"
          >
            <GripVertical className="h-4 w-4" />
          </button>

          {isRenaming ? (
            <input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={commitRename}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename()
                if (e.key === 'Escape') {
                  setTitleDraft(slide.title)
                  setIsRenaming(false)
                }
              }}
              className="min-w-0 flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
            />
          ) : (
            <h3
              onDoubleClick={() => setIsRenaming(true)}
              className="truncate text-sm font-semibold text-neutral-900"
              title="Double-click to rename"
            >
              {slide.title || `Slide ${slide.order}`}
            </h3>
          )}

          <Badge variant="navy">{SLIDE_TYPE_LABEL[slide.slide_type]}</Badge>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => setIsEditing((v) => !v)}
            aria-label="Edit slide"
            title="Edit"
            className={`rounded p-1.5 transition ${isEditing ? 'bg-brand-navy/10 text-brand-navy' : 'text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700'}`}
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onDuplicate}
            aria-label="Duplicate slide"
            title="Duplicate"
            className="rounded p-1.5 text-neutral-400 transition hover:bg-neutral-100 hover:text-neutral-700"
          >
            <Copy className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete slide"
            title="Delete"
            className="rounded p-1.5 text-neutral-400 transition hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {isEditing && slide.slide_type === 'CONTENT' && (
        <div className="mt-4">
          <label className="block text-xs font-medium text-neutral-500">Layout</label>
          <div className="mt-1.5">
            <LayoutPicker value={slide.layout} onChange={(layout) => void handleLayoutChange(layout)} />
          </div>
        </div>
      )}

      {isEditing && slide.slide_type === 'CONTENT' && (slide.layout === 'IMAGE_LEFT' || slide.layout === 'IMAGE_RIGHT') && (
        <div className="mt-4">
          <label className="block text-xs font-medium text-neutral-500">Image width</label>
          <p className="mt-0.5 text-xs text-neutral-400">
            How much of the slide the image column can use. The image still scales to its own proportions up to this
            cap — useful for widening a dense reference image (a table, a detailed diagram) so it stays legible.
          </p>
          <div className="mt-1.5">
            <ImageWidthPicker
              value={slide.image_column_width}
              onChange={(width) => void handleImageColumnWidthChange(width)}
            />
          </div>
        </div>
      )}

      {isEditing && slide.slide_type === 'CONTENT' && (
        <div className="mt-4">
          <label className="block text-xs font-medium text-neutral-500">Template</label>
          <p className="mt-0.5 text-xs text-neutral-400">
            Defaults to the course's template. Only set this to make this one slide deliberately differ.
          </p>
          <div className="mt-1.5">
            <TemplatePicker
              templates={templates}
              value={slide.template_override}
              onChange={(templateId) => void handleTemplateOverrideChange(templateId)}
              allowNone
              noneLabel="Use course template"
            />
          </div>
        </div>
      )}

      <div className="mt-4 space-y-3">
        {slide.slide_type === 'QUIZ' ? (
          isEditing ? (
            <QuizAuthoringPanel slideId={slide.id} defaultTitle={slide.title || `Slide ${slide.order}`} />
          ) : (
            <QuizSummaryPreview slideId={slide.id} />
          )
        ) : slide.slide_type === 'ASSIGNMENT' ? (
          isEditing ? (
            <AssignmentAuthoringPanel slideId={slide.id} />
          ) : (
            <AssignmentSummaryPreview slideId={slide.id} />
          )
        ) : slide.slide_type === 'SCENARIO' ? (
          isEditing ? (
            <ScenarioAuthoringPanel slideId={slide.id} />
          ) : (
            <ScenarioSummaryPreview slideId={slide.id} />
          )
        ) : !elements ? (
          <p className="text-sm text-neutral-500">Loading…</p>
        ) : elements.length === 0 ? (
          <p className="text-sm text-neutral-400">No content on this slide yet.</p>
        ) : isEditing ? (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleElementDragEnd(e)}>
            <SortableContext items={elements.map((el) => el.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {elements.map((element) => (
                  <SortableElementRow
                    key={element.id}
                    element={element}
                    onEdit={() => setEditingElement(element)}
                    onDelete={() => handleDeleteElement(element)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        ) : (
          <SlideElementsView elements={elements} layout={slide.layout} template={effectiveTemplate} />
        )}
      </div>

      {isEditing && (
        <div className="mt-4">
          <NarrationPanel slideId={slide.id} />
        </div>
      )}

      {isEditing && slide.slide_type === 'CONTENT' && (
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-dashed border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-600 transition hover:border-brand-navy hover:text-brand-navy"
        >
          <Plus className="h-4 w-4" />
          Add new element
        </button>
      )}

      {pickerOpen && (
        <ElementTypePicker
          onPick={(type) => {
            setPickerOpen(false)
            setPendingType(type)
          }}
          onClose={() => setPickerOpen(false)}
        />
      )}

      {pendingType && (
        <ElementFormModal
          slideId={slide.id}
          element={null}
          elementType={pendingType}
          nextOrder={(elements?.length ?? 0) + 1}
          template={effectiveTemplate}
          onSaved={() => {
            setPendingType(null)
            loadElements()
          }}
          onClose={() => setPendingType(null)}
        />
      )}

      {editingElement && (
        <ElementFormModal
          slideId={slide.id}
          element={editingElement}
          elementType={editingElement.element_type}
          nextOrder={editingElement.order}
          template={effectiveTemplate}
          onSaved={() => {
            setEditingElement(null)
            loadElements()
          }}
          onClose={() => setEditingElement(null)}
        />
      )}
    </Card>
  )
}
