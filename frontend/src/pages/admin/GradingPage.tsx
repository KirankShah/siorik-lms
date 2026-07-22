import { useEffect, useState } from 'react'
import { fetchUngradedAssignmentSubmissions, gradeAssignmentSubmission } from '../../lib/assignmentsApi'
import { fetchUngradedQuizAnswers, gradeQuizAnswer } from '../../lib/quizApi'
import type { AssignmentSubmission } from '../../types/assignment'
import type { QuizAnswerForGrading } from '../../types/quiz'

export function GradingPage() {
  const [quizAnswers, setQuizAnswers] = useState<QuizAnswerForGrading[]>([])
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>([])
  const [error, setError] = useState<string | null>(null)

  function load() {
    Promise.all([fetchUngradedQuizAnswers(), fetchUngradedAssignmentSubmissions()])
      .then(([answers, subs]) => {
        setQuizAnswers(answers)
        setSubmissions(subs)
      })
      .catch(() => setError('Could not load ungraded work.'))
  }

  useEffect(load, [])

  if (error) return <p className="text-sm text-red-600">{error}</p>

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-900">Grading</h1>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Short Answer / Essay Questions ({quizAnswers.length})</h2>
        <div className="mt-4 space-y-4">
          {quizAnswers.map((answer) => (
            <QuizAnswerGradingRow key={answer.id} answer={answer} onGraded={load} />
          ))}
          {quizAnswers.length === 0 && <p className="text-sm text-slate-400">Nothing to grade.</p>}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Assignment Submissions ({submissions.length})</h2>
        <div className="mt-4 space-y-4">
          {submissions.map((submission) => (
            <AssignmentSubmissionGradingRow key={submission.id} submission={submission} onGraded={load} />
          ))}
          {submissions.length === 0 && <p className="text-sm text-slate-400">Nothing to grade.</p>}
        </div>
      </section>
    </div>
  )
}

function QuizAnswerGradingRow({ answer, onGraded }: { answer: QuizAnswerForGrading; onGraded: () => void }) {
  const [marks, setMarks] = useState<number | ''>('')
  const [feedback, setFeedback] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleGrade() {
    if (marks === '') return
    setIsSaving(true)
    setError(null)
    try {
      await gradeQuizAnswer(answer.id, { marks_awarded: marks, grader_feedback: feedback })
      onGraded()
    } catch {
      setError(`Could not save grade. Marks must be between 0 and ${answer.question.marks}.`)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <p className="text-xs font-medium text-slate-400">
        {answer.user.first_name} {answer.user.last_name} ({answer.user.email}) — {answer.quiz_title}
      </p>
      <div className="mt-1 text-sm text-slate-900" dangerouslySetInnerHTML={{ __html: answer.question.question_text }} />
      <p className="mt-2 rounded bg-slate-50 p-2 text-sm whitespace-pre-wrap text-slate-700">{answer.text_response}</p>

      <div className="mt-3 flex items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-700">Marks (out of {answer.question.marks})</label>
          <input
            type="number"
            min={0}
            max={answer.question.marks}
            value={marks}
            onChange={(e) => setMarks(e.target.value === '' ? '' : Number(e.target.value))}
            className="mt-1 w-24 rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-700">Feedback</label>
          <input
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={() => void handleGrade()}
          disabled={isSaving || marks === ''}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
        >
          {isSaving ? 'Saving…' : 'Grade'}
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function AssignmentSubmissionGradingRow({ submission, onGraded }: { submission: AssignmentSubmission; onGraded: () => void }) {
  const [marks, setMarks] = useState<number | ''>('')
  const [feedback, setFeedback] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleGrade() {
    if (marks === '') return
    setIsSaving(true)
    setError(null)
    try {
      await gradeAssignmentSubmission(submission.id, { marks_awarded: marks, grader_feedback: feedback })
      onGraded()
    } catch {
      setError('Could not save grade.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <p className="text-xs font-medium text-slate-400">
        {submission.user.first_name} {submission.user.last_name} ({submission.user.email}) — submitted{' '}
        {new Date(submission.submitted_at).toLocaleString()}
      </p>
      {submission.text_response && <p className="mt-2 rounded bg-slate-50 p-2 text-sm whitespace-pre-wrap text-slate-700">{submission.text_response}</p>}
      {submission.file && (
        <a href={submission.file} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm text-slate-900 underline">
          Download submitted file
        </a>
      )}

      <div className="mt-3 flex items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-700">Marks</label>
          <input
            type="number"
            min={0}
            value={marks}
            onChange={(e) => setMarks(e.target.value === '' ? '' : Number(e.target.value))}
            className="mt-1 w-24 rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-700">Feedback</label>
          <input
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={() => void handleGrade()}
          disabled={isSaving || marks === ''}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
        >
          {isSaving ? 'Saving…' : 'Grade'}
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}
