import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { RichTextField } from './RichTextField'
import { createAssignment, fetchAssignmentForSlide, updateAssignment } from '../../lib/assignmentsApi'
import type { Assignment, SubmissionType } from '../../types/assignment'

interface AssignmentAuthoringPanelProps {
  slideId: number
}

export function AssignmentAuthoringPanel({ slideId }: AssignmentAuthoringPanelProps) {
  const [assignment, setAssignment] = useState<Assignment | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setIsLoading(true)
    fetchAssignmentForSlide(slideId)
      .then(setAssignment)
      .catch(() => setError('Could not load this assignment.'))
      .finally(() => setIsLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [slideId])

  async function handleCreate() {
    try {
      const created = await createAssignment({
        slide: slideId,
        instructions: '',
        submission_type: 'FILE_UPLOAD',
        max_marks: 100,
        due_offset_days: null,
      })
      setAssignment(created)
    } catch {
      setError('Could not create assignment.')
    }
  }

  if (isLoading) return <p className="text-sm text-neutral-500">Loading assignment…</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>

  if (!assignment) {
    return (
      <div className="rounded-xl border border-dashed border-neutral-300 p-6 text-center">
        <p className="text-sm text-neutral-500">This slide doesn't have an assignment yet.</p>
        <Button size="sm" className="mt-3" onClick={() => void handleCreate()}>
          Create assignment
        </Button>
      </div>
    )
  }

  return <AssignmentEditor key={assignment.id} assignment={assignment} onChanged={load} />
}

function AssignmentEditor({ assignment, onChanged }: { assignment: Assignment; onChanged: () => void }) {
  const [instructions, setInstructions] = useState(assignment.instructions)
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
        instructions,
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
      <h3 className="text-sm font-semibold text-neutral-900">Assignment</h3>

      <div>
        <label className="block text-xs font-medium text-neutral-700">Instructions</label>
        <div className="mt-1">
          <RichTextField
            key={assignment.id}
            initialHtml={instructions}
            onChange={setInstructions}
            placeholder="What should learners do for this assignment?"
            minHeight="140px"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className="block text-xs font-medium text-neutral-700">Submission type</label>
          <select
            value={submissionType}
            onChange={(e) => setSubmissionType(e.target.value as SubmissionType)}
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="FILE_UPLOAD">File upload</option>
            <option value="TEXT">Text response</option>
          </select>
        </div>
        <Input
          id={`assignment-max-marks-${assignment.id}`}
          label="Max marks"
          type="number"
          value={maxMarks}
          onChange={(e) => setMaxMarks(Number(e.target.value))}
        />
        <Input
          id={`assignment-due-${assignment.id}`}
          label="Due (days after enrollment)"
          type="number"
          value={dueOffsetDays}
          onChange={(e) => setDueOffsetDays(e.target.value === '' ? '' : Number(e.target.value))}
          placeholder="No due date"
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {saveSuccess && <p className="text-sm text-emerald-600">Saved.</p>}

      <Button onClick={() => void handleSave()} disabled={isSaving}>
        {isSaving ? 'Saving…' : 'Save assignment'}
      </Button>
    </div>
  )
}
