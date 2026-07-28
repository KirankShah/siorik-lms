import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import {
  createAssignmentSubmission,
  fetchAssignmentForSlide,
  fetchMySubmissions,
} from '../../lib/assignmentsApi'
import type { Assignment, AssignmentSubmission } from '../../types/assignment'
import type { SlideSummary } from '../../types/slides'

interface AssignmentSlidePlayerProps {
  slide: SlideSummary
  onSubmitted: () => void
}

export function AssignmentSlidePlayer({ slide, onSubmitted }: AssignmentSlidePlayerProps) {
  const [assignment, setAssignment] = useState<Assignment | null | undefined>(undefined)
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>([])
  const [error, setError] = useState<string | null>(null)

  function load() {
    fetchAssignmentForSlide(slide.id)
      .then(async (found) => {
        setAssignment(found)
        if (found) setSubmissions(await fetchMySubmissions(found.id))
      })
      .catch(() => setError('Could not load this assignment.'))
  }

  useEffect(() => {
    setAssignment(undefined)
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slide.id])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (assignment === undefined) return <p className="text-sm text-neutral-500">Loading assignment…</p>
  if (assignment === null) return <p className="text-sm text-neutral-400 italic">This assignment hasn't been set up yet.</p>

  return (
    <AssignmentSlidePlayerLoaded
      assignment={assignment}
      submissions={submissions}
      onSubmitted={() => {
        load()
        onSubmitted()
      }}
    />
  )
}

function AssignmentSlidePlayerLoaded({
  assignment,
  submissions,
  onSubmitted,
}: {
  assignment: Assignment
  submissions: AssignmentSubmission[]
  onSubmitted: () => void
}) {
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
    } catch {
      setSubmitError('Could not submit. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div>
      <Card
        className="text-sm text-neutral-700"
        dangerouslySetInnerHTML={{ __html: assignment.instructions || '<span class="text-neutral-400">No instructions provided.</span>' }}
      />

      {submissions.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-neutral-500">Your submissions</p>
          {submissions.map((submission) => (
            <div key={submission.id} className="rounded-md border border-neutral-200 p-3 text-sm">
              <p className="text-xs text-neutral-400">{new Date(submission.submitted_at).toLocaleString()}</p>
              {submission.text_response && <p className="mt-1 whitespace-pre-wrap text-neutral-700">{submission.text_response}</p>}
              {submission.file && (
                <a href={submission.file} target="_blank" rel="noreferrer" className="mt-1 inline-block text-brand-navy underline">
                  View submitted file
                </a>
              )}
              {submission.graded_at ? (
                <p className="mt-2 rounded bg-emerald-50 px-2 py-1 text-emerald-700">
                  Graded: {submission.marks_awarded} / {assignment.max_marks}
                  {submission.grader_feedback && ` — ${submission.grader_feedback}`}
                </p>
              ) : (
                <p className="mt-2 text-xs text-neutral-400">Awaiting grading.</p>
              )}
            </div>
          ))}
        </div>
      )}

      <Card className="mt-4">
        <p className="text-sm font-medium text-neutral-900">Submit your work</p>
        {assignment.submission_type === 'TEXT' ? (
          <textarea
            value={textResponse}
            onChange={(e) => setTextResponse(e.target.value)}
            rows={5}
            placeholder="Type your response…"
            className="mt-2 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
          />
        ) : (
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-2 w-full text-sm" />
        )}
        {submitError && <p className="mt-2 text-xs text-red-600">{submitError}</p>}
        <Button
          className="mt-3"
          onClick={() => void handleSubmit()}
          disabled={isSubmitting || (assignment.submission_type === 'TEXT' ? !textResponse.trim() : !file)}
        >
          {isSubmitting ? 'Submitting…' : 'Submit'}
        </Button>
      </Card>
    </div>
  )
}
