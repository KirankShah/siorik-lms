import { useState } from 'react'
import type { FormEvent } from 'react'
import { createLesson, updateLesson } from '../../lib/coursesApi'
import type { Lesson, LessonType } from '../../types/courses'

interface LessonFormProps {
  moduleId: number
  lesson?: Lesson
  // Order value to assign when creating a new lesson (position is finalized by a
  // follow-up reorder call from the parent, so this just needs to be a safe,
  // collision-free value — the parent passes lessons.length + 1).
  nextOrder?: number
  onSaved: (createdLessonId?: number) => void
  onCancel: () => void
}

const LESSON_TYPES: LessonType[] = ['VIDEO', 'SLIDES', 'DOCUMENT', 'TEXT']

export function LessonForm({ moduleId, lesson, nextOrder, onSaved, onCancel }: LessonFormProps) {
  const [title, setTitle] = useState(lesson?.title ?? '')
  const [lessonType, setLessonType] = useState<LessonType>(lesson?.lesson_type ?? 'TEXT')
  const [estimatedMinutes, setEstimatedMinutes] = useState(lesson?.estimated_minutes ?? 0)
  const [contentUrl, setContentUrl] = useState(lesson?.content_url ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setIsSaving(true)
    setError(null)
    try {
      const payload = {
        module: moduleId,
        title,
        lesson_type: lessonType,
        // Position (order) is owned by drag-and-drop / "add lesson here" — never hand-edited here.
        order: lesson ? lesson.order : (nextOrder ?? 1),
        estimated_minutes: estimatedMinutes,
        content_url: contentUrl,
        content_file: file,
      }
      if (lesson) {
        await updateLesson(lesson.id, payload)
        onSaved()
      } else {
        const created = await createLesson(payload)
        onSaved(created.id)
      }
    } catch {
      setError('Could not save the lesson — check the file type matches the lesson type (VIDEO: mp4/mov/webm, SLIDES: pdf/pptx, DOCUMENT: pdf/docx).')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 rounded-md border border-neutral-200 bg-neutral-50 p-3">
      <div className="grid grid-cols-2 gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Lesson title"
          required
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <select
          value={lessonType}
          onChange={(e) => setLessonType(e.target.value as LessonType)}
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        >
          {LESSON_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <input
          type="number"
          value={estimatedMinutes}
          onChange={(e) => setEstimatedMinutes(Number(e.target.value))}
          placeholder="Minutes"
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <input
          value={contentUrl}
          onChange={(e) => setContentUrl(e.target.value)}
          placeholder="Content URL (optional)"
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="col-span-2 text-xs" />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-3">
        <button type="submit" disabled={isSaving} className="text-sm font-medium text-brand-navy disabled:opacity-60">
          {isSaving ? 'Saving…' : 'Save'}
        </button>
        <button type="button" onClick={onCancel} className="text-sm text-neutral-500">
          Cancel
        </button>
      </div>
    </form>
  )
}
