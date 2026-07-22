import { useEffect, useState } from 'react'
import '@blocknote/core/fonts/inter.css'
import { useCreateBlockNote } from '@blocknote/react'
import { BlockNoteView } from '@blocknote/mantine'
import '@blocknote/mantine/style.css'
import { createAssignment, fetchAssignmentForPage, updateAssignment } from '../../lib/assignmentsApi'
import type { Assignment, SubmissionType } from '../../types/assignment'

interface AssignmentAuthoringPanelProps {
  pageId: number
}

export function AssignmentAuthoringPanel({ pageId }: AssignmentAuthoringPanelProps) {
  const [assignment, setAssignment] = useState<Assignment | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setIsLoading(true)
    fetchAssignmentForPage(pageId)
      .then(setAssignment)
      .catch(() => setError('Could not load this assignment.'))
      .finally(() => setIsLoading(false))
  }

  useEffect(load, [pageId])

  async function handleCreate() {
    try {
      const created = await createAssignment({
        page: pageId,
        instructions_json: [],
        submission_type: 'FILE_UPLOAD',
        max_marks: 100,
        due_offset_days: null,
      })
      setAssignment(created)
    } catch {
      setError('Could not create assignment.')
    }
  }

  if (isLoading) return <p className="text-sm text-slate-500">Loading assignment…</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>

  if (!assignment) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center">
        <p className="text-sm text-slate-500">This page doesn't have an assignment yet.</p>
        <button type="button" onClick={() => void handleCreate()} className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white">
          Create assignment
        </button>
      </div>
    )
  }

  return <AssignmentEditor key={assignment.id} assignment={assignment} onChanged={load} />
}

function AssignmentEditor({ assignment, onChanged }: { assignment: Assignment; onChanged: () => void }) {
  const editor = useCreateBlockNote({
    initialContent: assignment.instructions_json.length > 0 ? (assignment.instructions_json as never) : undefined,
  })

  const [submissionType, setSubmissionType] = useState<SubmissionType>(assignment.submission_type)
  const [maxMarks, setMaxMarks] = useState(assignment.max_marks)
  const [dueOffsetDays, setDueOffsetDays] = useState<number | ''>(assignment.due_offset_days ?? '')
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    setIsSaving(true)
    setSaveSuccess(false)
    setError(null)
    try {
      await updateAssignment(assignment.id, {
        instructions_json: editor.document,
        submission_type: submissionType,
        max_marks: maxMarks,
        due_offset_days: dueOffsetDays === '' ? null : Number(dueOffsetDays),
      })
      setSaveSuccess(true)
      onChanged()
    } catch {
      setError('Could not save assignment.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-slate-900">Assignment</h2>

      <div>
        <label className="block text-xs font-medium text-slate-700">Instructions</label>
        <div className="mt-1 rounded-xl border border-slate-200 bg-white">
          <BlockNoteView editor={editor} theme="light" />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-medium text-slate-700">Submission type</label>
          <select
            value={submissionType}
            onChange={(e) => setSubmissionType(e.target.value as SubmissionType)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="FILE_UPLOAD">File upload</option>
            <option value="TEXT">Text response</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-700">Max marks</label>
          <input
            type="number"
            value={maxMarks}
            onChange={(e) => setMaxMarks(Number(e.target.value))}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-700">Due (days after enrollment)</label>
          <input
            type="number"
            value={dueOffsetDays}
            onChange={(e) => setDueOffsetDays(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="No due date"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {saveSuccess && <p className="text-sm text-emerald-600">Saved.</p>}

      <button
        type="button"
        onClick={() => void handleSave()}
        disabled={isSaving}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
      >
        {isSaving ? 'Saving…' : 'Save Assignment'}
      </button>
    </div>
  )
}
