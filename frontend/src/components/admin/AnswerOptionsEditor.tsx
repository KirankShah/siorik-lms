import { useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent, ReactNode } from 'react'
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
import {
  createCategoryBucket,
  createCategorizeItem,
  createChoice,
  createHotspotRegion,
  deleteCategoryBucket,
  deleteCategorizeItem,
  deleteChoice,
  deleteHotspotRegion,
  updateCategoryBucket,
  updateCategorizeItem,
  updateChoice,
  updateHotspotRegion,
} from '../../lib/quizApi'
import type { CategoryBucket, CategorizeItem, Choice, HotspotRegion, QuestionType } from '../../types/quiz'

interface AnswerOptionsEditorProps {
  questionId: number
  questionType: QuestionType
  choices: Choice[]
  buckets: CategoryBucket[]
  categorizeItems: CategorizeItem[]
  image: string | null
  hotspotRegions: HotspotRegion[]
  onChanged: () => void
}

export function AnswerOptionsEditor({
  questionId,
  questionType,
  choices,
  buckets,
  categorizeItems,
  image,
  hotspotRegions,
  onChanged,
}: AnswerOptionsEditorProps) {
  const [error, setError] = useState<string | null>(null)

  async function withErrorHandling(action: () => Promise<unknown>, message: string) {
    try {
      await action()
      onChanged()
    } catch {
      setError(message)
    }
  }

  if (questionType === 'SHORT_ANSWER' || questionType === 'ESSAY') {
    return <p className="text-xs text-neutral-400 italic">Manually graded — no answer key needed. See the Grading page once learners submit.</p>
  }

  if (questionType === 'TRUE_FALSE') {
    return (
      <TrueFalseEditor
        questionId={questionId}
        choices={choices}
        onError={setError}
        errorNode={error && <p className="text-xs text-red-600">{error}</p>}
        onChanged={onChanged}
      />
    )
  }

  if (questionType === 'SINGLE_CHOICE' || questionType === 'MULTIPLE_CHOICE' || questionType === 'MULTIPLE_ANSWER') {
    return (
      <ChoiceListEditor
        questionId={questionId}
        choices={choices}
        exclusive={questionType === 'SINGLE_CHOICE' || questionType === 'MULTIPLE_CHOICE'}
        withErrorHandling={withErrorHandling}
        error={error}
      />
    )
  }

  if (questionType === 'FILL_BLANK') {
    return <FillBlankEditor questionId={questionId} choices={choices} withErrorHandling={withErrorHandling} error={error} />
  }

  if (questionType === 'MATCHING') {
    return <MatchingEditor questionId={questionId} choices={choices} withErrorHandling={withErrorHandling} error={error} />
  }

  if (questionType === 'CATEGORIZE') {
    return (
      <CategorizeEditor
        questionId={questionId}
        buckets={buckets}
        items={categorizeItems}
        withErrorHandling={withErrorHandling}
        error={error}
      />
    )
  }

  if (questionType === 'HOTSPOT') {
    return (
      <HotspotEditor
        questionId={questionId}
        image={image}
        regions={hotspotRegions}
        withErrorHandling={withErrorHandling}
        error={error}
      />
    )
  }

  // ORDERING
  return <OrderingEditor questionId={questionId} choices={choices} withErrorHandling={withErrorHandling} error={error} />
}

type ErrorHandler = (action: () => Promise<unknown>, message: string) => Promise<void>

function AddRowButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick} className="mt-2 text-xs font-medium text-brand-navy hover:underline">
      {label}
    </button>
  )
}

function RemoveButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="text-neutral-300 hover:text-red-500" aria-label="Remove">
      ✕
    </button>
  )
}

// SINGLE_CHOICE/MULTIPLE_CHOICE (radio-style, one correct answer) and
// MULTIPLE_ANSWER (checkbox-style, several correct answers).
function ChoiceListEditor({
  questionId,
  choices,
  exclusive,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  exclusive: boolean
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  async function handleAdd() {
    await withErrorHandling(
      () => createChoice({ question: questionId, choice_text: 'New option', is_correct: false, order: choices.length + 1 }),
      'Could not add option.',
    )
  }

  async function handleToggleCorrect(choice: Choice) {
    await withErrorHandling(async () => {
      if (exclusive) {
        await Promise.all(choices.filter((c) => c.id !== choice.id && c.is_correct).map((c) => updateChoice(c.id, { is_correct: false })))
      }
      await updateChoice(choice.id, { is_correct: !choice.is_correct })
    }, 'Could not update option.')
  }

  async function handleTextChange(choice: Choice, text: string) {
    await withErrorHandling(() => updateChoice(choice.id, { choice_text: text }), 'Could not update option.')
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove option.')
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2 text-xs text-neutral-400">
        <span className="w-16 shrink-0 font-medium text-neutral-500">Mark as correct</span>
        <span>
          {exclusive
            ? 'Select the radio button next to the correct option.'
            : 'Check the box next to every correct option (more than one is allowed).'}
        </span>
      </div>
      <ul className="space-y-1">
        {choices.map((choice) => (
          <li
            key={choice.id}
            className={`flex items-center gap-2 rounded-md border px-2 py-1.5 ${
              choice.is_correct ? 'border-emerald-300 bg-emerald-50' : 'border-transparent'
            }`}
          >
            <span className="flex w-16 shrink-0 items-center justify-center">
              <input
                type={exclusive ? 'radio' : 'checkbox'}
                name={`correct-${questionId}`}
                checked={choice.is_correct ?? false}
                onChange={() => void handleToggleCorrect(choice)}
                aria-label="Mark as correct"
                className="h-3.5 w-3.5"
              />
            </span>
            <input
              defaultValue={choice.choice_text}
              onBlur={(e) => e.target.value !== choice.choice_text && void handleTextChange(choice, e.target.value)}
              className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
            />
            <RemoveButton onClick={() => void handleRemove(choice.id)} />
          </li>
        ))}
      </ul>
      {choices.length === 0 && (
        <p className="mt-1 text-xs text-neutral-400">No options yet — add one below, then mark it correct.</p>
      )}
      <AddRowButton onClick={() => void handleAdd()} label="+ Add option" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function TrueFalseEditor({
  questionId,
  choices,
  onChanged,
  onError,
  errorNode,
}: {
  questionId: number
  choices: Choice[]
  onChanged: () => void
  onError: (message: string | null) => void
  errorNode: ReactNode
}) {
  async function ensureSeeded() {
    if (choices.length > 0) return choices
    const created = await Promise.all([
      createChoice({ question: questionId, choice_text: 'True', is_correct: true, order: 1 }),
      createChoice({ question: questionId, choice_text: 'False', is_correct: false, order: 2 }),
    ])
    onChanged()
    return created
  }

  async function handleSelect(label: 'True' | 'False') {
    try {
      const current = await ensureSeeded()
      const target = choices.length > 0 ? choices : (current as unknown as Choice[])
      await Promise.all(target.map((c) => updateChoice(c.id, { is_correct: c.choice_text === label })))
      onChanged()
    } catch {
      onError('Could not update answer.')
    }
  }

  const trueChoice = choices.find((c) => c.choice_text === 'True')
  const falseChoice = choices.find((c) => c.choice_text === 'False')

  return (
    <div>
      <p className="mb-1.5 text-xs text-neutral-400">Select which answer is correct.</p>
      <div className="flex gap-2 text-sm">
        <label
          className={`flex flex-1 cursor-pointer items-center gap-1.5 rounded-md border px-3 py-1.5 ${
            trueChoice?.is_correct ? 'border-emerald-300 bg-emerald-50' : 'border-neutral-200'
          }`}
        >
          <input
            type="radio"
            name={`tf-${questionId}`}
            checked={trueChoice?.is_correct ?? false}
            onChange={() => void handleSelect('True')}
          />
          True
        </label>
        <label
          className={`flex flex-1 cursor-pointer items-center gap-1.5 rounded-md border px-3 py-1.5 ${
            falseChoice?.is_correct ? 'border-emerald-300 bg-emerald-50' : 'border-neutral-200'
          }`}
        >
          <input
            type="radio"
            name={`tf-${questionId}`}
            checked={falseChoice?.is_correct ?? false}
            onChange={() => void handleSelect('False')}
          />
          False
        </label>
      </div>
      {errorNode}
    </div>
  )
}

function FillBlankEditor({
  questionId,
  choices,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  async function handleAdd() {
    await withErrorHandling(
      () => createChoice({ question: questionId, choice_text: '', is_correct: true, order: choices.length + 1 }),
      'Could not add accepted answer.',
    )
  }

  async function handleTextChange(choice: Choice, text: string) {
    await withErrorHandling(() => updateChoice(choice.id, { choice_text: text }), 'Could not update accepted answer.')
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove accepted answer.')
  }

  return (
    <div>
      <p className="mb-1 text-xs text-neutral-400">Accepted answers (the learner's typed answer is matched against any of these, case-insensitively):</p>
      <ul className="space-y-1">
        {choices.map((choice) => (
          <li key={choice.id} className="flex items-center gap-2">
            <input
              defaultValue={choice.choice_text}
              onBlur={(e) => e.target.value !== choice.choice_text && void handleTextChange(choice, e.target.value)}
              placeholder="Accepted answer"
              className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
            />
            <RemoveButton onClick={() => void handleRemove(choice.id)} />
          </li>
        ))}
      </ul>
      <AddRowButton onClick={() => void handleAdd()} label="+ Add accepted answer" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function SortableMatchingRow({
  choice,
  onChange,
  onRemove,
}: {
  choice: Choice
  onChange: (choice: Choice, field: 'choice_text' | 'match_text', value: string) => void
  onRemove: (choiceId: number) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: choice.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <li ref={setNodeRef} style={style} className="flex items-center gap-2">
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="shrink-0 cursor-grab touch-none text-neutral-300 hover:text-neutral-500"
        aria-label="Drag to reorder pair"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <input
        defaultValue={choice.choice_text}
        onBlur={(e) => e.target.value !== choice.choice_text && onChange(choice, 'choice_text', e.target.value)}
        placeholder="Item"
        className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
      />
      <span className="text-neutral-400">↔</span>
      <input
        defaultValue={choice.match_text ?? ''}
        onBlur={(e) => e.target.value !== choice.match_text && onChange(choice, 'match_text', e.target.value)}
        placeholder="Correct match"
        className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
      />
      <RemoveButton onClick={() => onRemove(choice.id)} />
    </li>
  )
}

function MatchingEditor({
  questionId,
  choices,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  const sorted = [...choices].sort((a, b) => a.order - b.order)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  async function handleAdd() {
    await withErrorHandling(
      () =>
        createChoice({
          question: questionId,
          choice_text: '',
          match_text: '',
          // Every pair is part of the answer key for MATCHING — there's no
          // per-row "correct" toggle like ChoiceListEditor's, the pairing
          // itself (choice_text <-> match_text) is what's graded.
          is_correct: true,
          order: sorted.length + 1,
        }),
      'Could not add pair.',
    )
  }

  async function handleChange(choice: Choice, field: 'choice_text' | 'match_text', value: string) {
    await withErrorHandling(() => updateChoice(choice.id, { [field]: value }), 'Could not update pair.')
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove pair.')
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = sorted.findIndex((c) => c.id === active.id)
    const newIndex = sorted.findIndex((c) => c.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reordered = arrayMove(sorted, oldIndex, newIndex)
    await withErrorHandling(
      () => Promise.all(reordered.map((choice, index) => updateChoice(choice.id, { order: index + 1 }))),
      'Could not reorder pairs.',
    )
  }

  return (
    <div>
      <p className="mb-1 text-xs text-neutral-400">Pairs (left matches right):</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleDragEnd(e)}>
        <SortableContext items={sorted.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          <ul className="space-y-1">
            {sorted.map((choice) => (
              <SortableMatchingRow
                key={choice.id}
                choice={choice}
                onChange={(c, field, value) => void handleChange(c, field, value)}
                onRemove={(id) => void handleRemove(id)}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
      <AddRowButton onClick={() => void handleAdd()} label="+ Add pair" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function SortableOrderingRow({
  choice,
  index,
  onTextChange,
  onRemove,
}: {
  choice: Choice
  index: number
  onTextChange: (choice: Choice, text: string) => void
  onRemove: (choiceId: number) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: choice.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <li ref={setNodeRef} style={style} className="flex items-center gap-2">
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="shrink-0 cursor-grab touch-none text-neutral-300 hover:text-neutral-500"
        aria-label="Drag to reorder item"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <span className="w-4 shrink-0 text-xs text-neutral-400">{index + 1}.</span>
      <input
        defaultValue={choice.choice_text}
        onBlur={(e) => e.target.value !== choice.choice_text && onTextChange(choice, e.target.value)}
        placeholder="Item"
        className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
      />
      <RemoveButton onClick={() => onRemove(choice.id)} />
    </li>
  )
}

function OrderingEditor({
  questionId,
  choices,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  const sorted = [...choices].sort((a, b) => a.order - b.order)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  async function handleAdd() {
    await withErrorHandling(
      () => createChoice({ question: questionId, choice_text: '', order: sorted.length + 1 }),
      'Could not add item.',
    )
  }

  async function handleTextChange(choice: Choice, text: string) {
    await withErrorHandling(() => updateChoice(choice.id, { choice_text: text }), 'Could not update item.')
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove item.')
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = sorted.findIndex((c) => c.id === active.id)
    const newIndex = sorted.findIndex((c) => c.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reordered = arrayMove(sorted, oldIndex, newIndex)
    await withErrorHandling(
      () => Promise.all(reordered.map((choice, index) => updateChoice(choice.id, { order: index + 1 }))),
      'Could not reorder items.',
    )
  }

  return (
    <div>
      <p className="mb-1 text-xs text-neutral-400">Items, dragged into the correct order:</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleDragEnd(e)}>
        <SortableContext items={sorted.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          <ul className="space-y-1">
            {sorted.map((choice, index) => (
              <SortableOrderingRow
                key={choice.id}
                choice={choice}
                index={index}
                onTextChange={(c, text) => void handleTextChange(c, text)}
                onRemove={(id) => void handleRemove(id)}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
      <AddRowButton onClick={() => void handleAdd()} label="+ Add item" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function SortableBucketRow({
  bucket,
  onChange,
  onRemove,
}: {
  bucket: CategoryBucket
  onChange: (bucket: CategoryBucket, label: string) => void
  onRemove: (bucketId: number) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: bucket.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <li ref={setNodeRef} style={style} className="flex items-center gap-2">
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="shrink-0 cursor-grab touch-none text-neutral-300 hover:text-neutral-500"
        aria-label="Drag to reorder bucket"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <input
        defaultValue={bucket.label}
        onBlur={(e) => e.target.value !== bucket.label && onChange(bucket, e.target.value)}
        placeholder="Bucket label"
        className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
      />
      <RemoveButton onClick={() => onRemove(bucket.id)} />
    </li>
  )
}

function SortableCategorizeItemRow({
  item,
  buckets,
  onTextChange,
  onImageChange,
  onBucketChange,
  onRemove,
}: {
  item: CategorizeItem
  buckets: CategoryBucket[]
  onTextChange: (item: CategorizeItem, text: string) => void
  onImageChange: (item: CategorizeItem, file: File) => void
  onBucketChange: (item: CategorizeItem, bucketId: number) => void
  onRemove: (itemId: number) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <li ref={setNodeRef} style={style} className="flex items-center gap-2">
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="shrink-0 cursor-grab touch-none text-neutral-300 hover:text-neutral-500"
        aria-label="Drag to reorder item"
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <input
        defaultValue={item.item_text}
        onBlur={(e) => e.target.value !== item.item_text && onTextChange(item, e.target.value)}
        placeholder="Item text"
        className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
      />
      {item.item_image ? (
        <span className="relative shrink-0">
          <img src={item.item_image} alt="" className="h-8 w-8 rounded border border-neutral-200 object-cover" />
        </span>
      ) : (
        <label className="shrink-0 cursor-pointer text-xs text-neutral-400 hover:text-brand-navy">
          + Image
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onImageChange(item, e.target.files[0])}
          />
        </label>
      )}
      <select
        value={item.correct_bucket ?? ''}
        onChange={(e) => onBucketChange(item, Number(e.target.value))}
        className="shrink-0 rounded border border-neutral-300 px-2 py-1 text-sm"
      >
        <option value="" disabled>
          Bucket…
        </option>
        {buckets.map((bucket) => (
          <option key={bucket.id} value={bucket.id}>
            {bucket.label}
          </option>
        ))}
      </select>
      <RemoveButton onClick={() => onRemove(item.id)} />
    </li>
  )
}

function CategorizeEditor({
  questionId,
  buckets,
  items,
  withErrorHandling,
  error,
}: {
  questionId: number
  buckets: CategoryBucket[]
  items: CategorizeItem[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  const sortedBuckets = [...buckets].sort((a, b) => a.order - b.order)
  const sortedItems = [...items].sort((a, b) => a.order - b.order)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  async function handleAddBucket() {
    await withErrorHandling(
      () => createCategoryBucket({ question: questionId, label: '', order: sortedBuckets.length + 1 }),
      'Could not add bucket.',
    )
  }

  async function handleBucketChange(bucket: CategoryBucket, label: string) {
    await withErrorHandling(() => updateCategoryBucket(bucket.id, { label }), 'Could not update bucket.')
  }

  async function handleRemoveBucket(bucketId: number) {
    await withErrorHandling(() => deleteCategoryBucket(bucketId), 'Could not remove bucket.')
  }

  async function handleBucketDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = sortedBuckets.findIndex((b) => b.id === active.id)
    const newIndex = sortedBuckets.findIndex((b) => b.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reordered = arrayMove(sortedBuckets, oldIndex, newIndex)
    await withErrorHandling(
      () => Promise.all(reordered.map((bucket, index) => updateCategoryBucket(bucket.id, { order: index + 1 }))),
      'Could not reorder buckets.',
    )
  }

  async function handleAddItem() {
    if (sortedBuckets.length === 0) return
    await withErrorHandling(
      () =>
        createCategorizeItem({
          question: questionId,
          item_text: '',
          correct_bucket: sortedBuckets[0].id,
          order: sortedItems.length + 1,
        }),
      'Could not add item.',
    )
  }

  async function handleItemTextChange(item: CategorizeItem, text: string) {
    await withErrorHandling(() => updateCategorizeItem(item.id, { item_text: text }), 'Could not update item.')
  }

  async function handleItemImageChange(item: CategorizeItem, file: File) {
    await withErrorHandling(() => updateCategorizeItem(item.id, { item_image: file }), 'Could not update item image.')
  }

  async function handleItemBucketChange(item: CategorizeItem, bucketId: number) {
    await withErrorHandling(() => updateCategorizeItem(item.id, { correct_bucket: bucketId }), 'Could not update item.')
  }

  async function handleRemoveItem(itemId: number) {
    await withErrorHandling(() => deleteCategorizeItem(itemId), 'Could not remove item.')
  }

  async function handleItemDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = sortedItems.findIndex((i) => i.id === active.id)
    const newIndex = sortedItems.findIndex((i) => i.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const reordered = arrayMove(sortedItems, oldIndex, newIndex)
    await withErrorHandling(
      () => Promise.all(reordered.map((item, index) => updateCategorizeItem(item.id, { order: index + 1 }))),
      'Could not reorder items.',
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-1 text-xs text-neutral-400">Buckets (2 or more):</p>
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleBucketDragEnd(e)}>
          <SortableContext items={sortedBuckets.map((b) => b.id)} strategy={verticalListSortingStrategy}>
            <ul className="space-y-1">
              {sortedBuckets.map((bucket) => (
                <SortableBucketRow
                  key={bucket.id}
                  bucket={bucket}
                  onChange={(b, label) => void handleBucketChange(b, label)}
                  onRemove={(id) => void handleRemoveBucket(id)}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
        <AddRowButton onClick={() => void handleAddBucket()} label="+ Add bucket" />
      </div>

      <div>
        <p className="mb-1 text-xs text-neutral-400">Items, each assigned to its correct bucket:</p>
        {sortedBuckets.length === 0 ? (
          <p className="text-xs italic text-neutral-400">Add at least 2 buckets first.</p>
        ) : (
          <>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleItemDragEnd(e)}>
              <SortableContext items={sortedItems.map((i) => i.id)} strategy={verticalListSortingStrategy}>
                <ul className="space-y-1">
                  {sortedItems.map((item) => (
                    <SortableCategorizeItemRow
                      key={item.id}
                      item={item}
                      buckets={sortedBuckets}
                      onTextChange={(i, text) => void handleItemTextChange(i, text)}
                      onImageChange={(i, file) => void handleItemImageChange(i, file)}
                      onBucketChange={(i, bucketId) => void handleItemBucketChange(i, bucketId)}
                      onRemove={(id) => void handleRemoveItem(id)}
                    />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
            <AddRowButton onClick={() => void handleAddItem()} label="+ Add item" />
          </>
        )}
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value))
}

interface DrawPoint {
  x: number
  y: number
}

function HotspotEditor({
  questionId,
  image,
  regions,
  withErrorHandling,
  error,
}: {
  questionId: number
  image: string | null
  regions: HotspotRegion[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [drawStart, setDrawStart] = useState<DrawPoint | null>(null)
  const [drawCurrent, setDrawCurrent] = useState<DrawPoint | null>(null)

  function pointFromEvent(e: ReactMouseEvent): DrawPoint | null {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return null
    return {
      x: clampPercent(((e.clientX - rect.left) / rect.width) * 100),
      y: clampPercent(((e.clientY - rect.top) / rect.height) * 100),
    }
  }

  function handleMouseDown(e: ReactMouseEvent) {
    const point = pointFromEvent(e)
    if (!point) return
    setDrawStart(point)
    setDrawCurrent(point)
  }

  function handleMouseMove(e: ReactMouseEvent) {
    if (!drawStart) return
    const point = pointFromEvent(e)
    if (point) setDrawCurrent(point)
  }

  async function handleMouseUp() {
    if (!drawStart || !drawCurrent) return
    const x = Math.min(drawStart.x, drawCurrent.x)
    const y = Math.min(drawStart.y, drawCurrent.y)
    const width = Math.abs(drawCurrent.x - drawStart.x)
    const height = Math.abs(drawCurrent.y - drawStart.y)
    setDrawStart(null)
    setDrawCurrent(null)
    // Ignore accidental clicks that didn't really drag out a box.
    if (width < 1 || height < 1) return
    await withErrorHandling(
      () => createHotspotRegion({ question: questionId, x, y, width, height, is_correct: false }),
      'Could not add region.',
    )
  }

  async function handleToggleCorrect(region: HotspotRegion) {
    await withErrorHandling(
      () => updateHotspotRegion(region.id, { is_correct: !region.is_correct }),
      'Could not update region.',
    )
  }

  async function handleRemove(regionId: number) {
    await withErrorHandling(() => deleteHotspotRegion(regionId), 'Could not remove region.')
  }

  if (!image) {
    return <p className="text-xs italic text-neutral-400">Upload an image above, then draw regions on it here.</p>
  }

  const previewBox =
    drawStart && drawCurrent
      ? {
          left: Math.min(drawStart.x, drawCurrent.x),
          top: Math.min(drawStart.y, drawCurrent.y),
          width: Math.abs(drawCurrent.x - drawStart.x),
          height: Math.abs(drawCurrent.y - drawStart.y),
        }
      : null

  return (
    <div>
      <p className="mb-1 text-xs text-neutral-400">
        Click and drag on the image to draw a region, then mark it correct or incorrect:
      </p>
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={() => void handleMouseUp()}
        onMouseLeave={() => {
          setDrawStart(null)
          setDrawCurrent(null)
        }}
        className="relative inline-block max-w-full cursor-crosshair select-none"
      >
        <img src={image} alt="" className="block max-w-full rounded border border-neutral-200" draggable={false} />
        {regions.map((region) => (
          <div
            key={region.id}
            onMouseDown={(e) => e.stopPropagation()}
            className={`group absolute border-2 ${
              region.is_correct ? 'border-emerald-500 bg-emerald-500/10' : 'border-red-400 bg-red-400/10'
            }`}
            style={{ left: `${region.x}%`, top: `${region.y}%`, width: `${region.width}%`, height: `${region.height}%` }}
          >
            <div className="absolute -top-6 left-0 flex gap-1 opacity-0 transition group-hover:opacity-100">
              <button
                type="button"
                onClick={() => void handleToggleCorrect(region)}
                className="rounded border border-neutral-200 bg-white px-1.5 py-0.5 text-[10px] font-medium shadow"
              >
                {region.is_correct ? 'Correct' : 'Incorrect'}
              </button>
              <button
                type="button"
                onClick={() => void handleRemove(region.id)}
                className="rounded border border-neutral-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-red-600 shadow"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
        {previewBox && (
          <div
            className="pointer-events-none absolute border-2 border-dashed border-brand-navy bg-brand-navy/10"
            style={{
              left: `${previewBox.left}%`,
              top: `${previewBox.top}%`,
              width: `${previewBox.width}%`,
              height: `${previewBox.height}%`,
            }}
          />
        )}
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}
