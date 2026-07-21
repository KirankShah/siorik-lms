import { useState } from 'react'
import { deleteLesson, deleteModule, updateModule } from '../../lib/coursesApi'
import type { Lesson, Module } from '../../types/courses'
import { LessonForm } from './LessonForm'

interface ModuleEditorProps {
  module: Module
  onChanged: () => void
}

export function ModuleEditor({ module, onChanged }: ModuleEditorProps) {
  const [isEditingModule, setIsEditingModule] = useState(false)
  const [title, setTitle] = useState(module.title)
  const [order, setOrder] = useState(module.order)
  const [editingLessonId, setEditingLessonId] = useState<number | null>(null)
  const [isAddingLesson, setIsAddingLesson] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSaveModule() {
    try {
      await updateModule(module.id, { title, order })
      setIsEditingModule(false)
      onChanged()
    } catch {
      setError('Could not update module.')
    }
  }

  async function handleDeleteModule() {
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

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between">
        {isEditingModule ? (
          <div className="flex flex-1 items-center gap-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <input
              type="number"
              value={order}
              onChange={(e) => setOrder(Number(e.target.value))}
              className="w-16 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button onClick={handleSaveModule} className="text-sm font-medium text-emerald-700">
              Save
            </button>
            <button onClick={() => setIsEditingModule(false)} className="text-sm text-slate-500">
              Cancel
            </button>
          </div>
        ) : (
          <h3 className="text-sm font-semibold text-slate-900">
            {module.order}. {module.title}
          </h3>
        )}
        {!isEditingModule && (
          <div className="flex gap-3 text-sm">
            <button type="button" onClick={() => setIsEditingModule(true)} className="text-slate-600 hover:underline">
              Edit
            </button>
            <button type="button" onClick={handleDeleteModule} className="text-red-600 hover:underline">
              Delete
            </button>
          </div>
        )}
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <ul className="mt-3 space-y-2">
        {module.lessons.map((lesson) => (
          <li key={lesson.id}>
            {editingLessonId === lesson.id ? (
              <LessonForm
                moduleId={module.id}
                lesson={lesson}
                onSaved={() => {
                  setEditingLessonId(null)
                  onChanged()
                }}
                onCancel={() => setEditingLessonId(null)}
              />
            ) : (
              <div className="flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 text-sm">
                <span>
                  {lesson.order}. {lesson.title} <span className="text-xs text-slate-400">({lesson.lesson_type})</span>
                </span>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setEditingLessonId(lesson.id)}
                    className="text-slate-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button type="button" onClick={() => handleDeleteLesson(lesson)} className="text-red-600 hover:underline">
                    Delete
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>

      {isAddingLesson ? (
        <div className="mt-3">
          <LessonForm
            moduleId={module.id}
            onSaved={() => {
              setIsAddingLesson(false)
              onChanged()
            }}
            onCancel={() => setIsAddingLesson(false)}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setIsAddingLesson(true)}
          className="mt-3 text-sm font-medium text-slate-900 hover:underline"
        >
          + Add lesson
        </button>
      )}
    </div>
  )
}
