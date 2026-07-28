import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { fetchAssignmentForSlide } from '../../lib/assignmentsApi'
import type { Assignment } from '../../types/assignment'

const SUBMISSION_TYPE_LABEL = { FILE_UPLOAD: 'File upload', TEXT: 'Text response' }

export function AssignmentSummaryPreview({ slideId }: { slideId: number }) {
  const [assignment, setAssignment] = useState<Assignment | null | undefined>(undefined)

  useEffect(() => {
    setAssignment(undefined)
    fetchAssignmentForSlide(slideId)
      .then(setAssignment)
      .catch(() => setAssignment(null))
  }, [slideId])

  if (assignment === undefined) return <p className="text-sm text-neutral-500">Loading…</p>

  if (!assignment) {
    return (
      <div className="flex items-center gap-2 text-sm text-neutral-400">
        <FileText className="h-4 w-4" />
        No assignment yet — click edit to create one.
      </div>
    )
  }

  return (
    <div>
      {assignment.instructions ? (
        <div
          className="line-clamp-2 text-sm text-neutral-700"
          dangerouslySetInnerHTML={{ __html: assignment.instructions }}
        />
      ) : (
        <p className="text-sm text-neutral-400">No instructions written yet.</p>
      )}
      <div className="mt-1.5 flex flex-wrap gap-2">
        <Badge variant="navy">{SUBMISSION_TYPE_LABEL[assignment.submission_type]}</Badge>
        <Badge>{assignment.max_marks} marks</Badge>
        {assignment.due_offset_days !== null && <Badge>Due {assignment.due_offset_days} days after enrollment</Badge>}
      </div>
    </div>
  )
}
