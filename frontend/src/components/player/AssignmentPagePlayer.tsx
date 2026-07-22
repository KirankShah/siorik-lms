import { useEffect, useState } from 'react'
import { useCreateBlockNote } from '@blocknote/react'
import { BlockNoteView } from '@blocknote/mantine'
import '@blocknote/core/fonts/inter.css'
import '@blocknote/mantine/style.css'
import { savePageProgress } from '../../lib/coursesApi'
import { createAssignmentSubmission, fetchAssignmentForPage, fetchMySubmissions } from '../../lib/assignmentsApi'
import type { Enrollment, PageProgress, PageSummary } from '../../types/courses'
import type { Assignment, AssignmentSubmission } from '../../types/assignment'
import { PageNavFooter } from './PageNavFooter'

interface AssignmentPagePlayerProps {
  page: PageSummary
  enrollmentId: number
  existingProgress: PageProgress | undefined
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  onProgressSynced: (enrollment: Enrollment) => void
}

export function AssignmentPagePlayer({
  page,
  enrollmentId,
  existingProgress,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onProgressSynced,
}: AssignmentPagePlayerProps) {
  const [assignment, setAssignment] = useState<Assignment | null | undefined>(undefined)
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>([])
  const [error, setError] = useState<string | null>(null)

  function load() {
    fetchAssignmentForPage(page.id)
      .then(async (found) => {
        setAssignment(found)
        if (found) setSubmissions(await fetchMySubmissions(found.id))
      })
      .catch(() => setError('Could not load this assignment.'))
  }

  useEffect(load, [page.id])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (assignment === undefined) return <p className="text-sm text-slate-500">Loading assignment…</p>
  if (assignment === null) return <p className="text-sm text-slate-400 italic">This assignment hasn't been set up yet.</p>

  return (
    <AssignmentPagePlayerLoaded
      assignment={assignment}
      submissions={submissions}
      enrollmentId={enrollmentId}
      pageId={page.id}
      existingProgress={existingProgress}
      hasPrevious={hasPrevious}
      hasNext={hasNext}
      onPrevious={onPrevious}
      onNext={onNext}
      onProgressSynced={onProgressSynced}
      onSubmitted={load}
    />
  )
}

function AssignmentPagePlayerLoaded({
  assignment,
  submissions,
  enrollmentId,
  pageId,
  existingProgress,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onProgressSynced,
  onSubmitted,
}: {
  assignment: Assignment
  submissions: AssignmentSubmission[]
  enrollmentId: number
  pageId: number
  existingProgress: PageProgress | undefined
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  onProgressSynced: (enrollment: Enrollment) => void
  onSubmitted: () => void
}) {
  const editor = useCreateBlockNote({
    initialContent: assignment.instructions_json.length > 0 ? (assignment.instructions_json as never) : undefined,
  })

  const [textResponse, setTextResponse] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  async function handleSubmit() {
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      await createAssignmentSubmission({ assignment: assignment.id, text_response: textResponse, file })
      setTextResponse('')
      setFile(null)
      onSubmitted()
      if (!existingProgress?.completed_at) {
        const enrollment = await savePageProgress(enrollmentId, { page: pageId, completed: true })
        onProgressSynced(enrollment)
      }
    } catch {
      setSubmitError('Could not submit. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div>
      <div className="rounded-xl border border-slate-200 bg-white">
        <BlockNoteView editor={editor} editable={false} theme="light" />
      </div>

      {submissions.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-slate-500">Your submissions</p>
          {submissions.map((submission) => (
            <div key={submission.id} className="rounded-md border border-slate-200 p-3 text-sm">
              <p className="text-xs text-slate-400">{new Date(submission.submitted_at).toLocaleString()}</p>
              {submission.text_response && <p className="mt-1 whitespace-pre-wrap text-slate-700">{submission.text_response}</p>}
              {submission.file && (
                <a href={submission.file} target="_blank" rel="noreferrer" className="mt-1 inline-block text-slate-900 underline">
                  View submitted file
                </a>
              )}
              {submission.graded_at ? (
                <p className="mt-2 rounded bg-emerald-50 px-2 py-1 text-emerald-700">
                  Graded: {submission.marks_awarded} / {assignment.max_marks}
                  {submission.grader_feedback && ` — ${submission.grader_feedback}`}
                </p>
              ) : (
                <p className="mt-2 text-xs text-slate-400">Awaiting grading.</p>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 rounded-lg border border-slate-200 p-4">
        <p className="text-sm font-medium text-slate-900">Submit your work</p>
        {assignment.submission_type === 'TEXT' ? (
          <textarea
            value={textResponse}
            onChange={(e) => setTextResponse(e.target.value)}
            rows={5}
            placeholder="Type your response…"
            className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        ) : (
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-2 w-full text-sm"
          />
        )}
        {submitError && <p className="mt-2 text-xs text-red-600">{submitError}</p>}
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={isSubmitting || (assignment.submission_type === 'TEXT' ? !textResponse.trim() : !file)}
          className="mt-3 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? 'Submitting…' : 'Submit'}
        </button>
      </div>

      <PageNavFooter hasPrevious={hasPrevious} hasNext={hasNext} onPrevious={onPrevious} onNext={onNext} />
    </div>
  )
}
