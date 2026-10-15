import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { fetchPeriodicExamResult, fetchPeriodicExamSummary } from '../lib/periodicExamsApi'
import type { PeriodicExamLearnerSummary, PeriodicExamResult } from '../types/periodicExams'

export function PeriodicExamResultPage() {
  const { attemptId } = useParams()
  const [result, setResult] = useState<PeriodicExamResult | null>(null)
  const [summary, setSummary] = useState<PeriodicExamLearnerSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const id = Number(attemptId)
    if (!Number.isInteger(id)) {
      setError('This result could not be found.')
      return
    }
    Promise.all([fetchPeriodicExamResult(id), fetchPeriodicExamSummary()])
      .then(([resultValue, summaryValue]) => {
        setResult(resultValue)
        setSummary(summaryValue)
      })
      .catch(() => setError('This result could not be loaded.'))
  }, [attemptId])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!result || !summary) return <p className="text-sm text-neutral-500">Loading result…</p>

  return (
    <Card className="mx-auto max-w-xl text-center">
      {result.passed ? <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-600" /> : <XCircle className="mx-auto h-14 w-14 text-red-500" />}
      <p className="mt-4 text-sm font-semibold tracking-wide text-neutral-500 uppercase">Periodic Exam result</p>
      <h1 className="mt-2 text-3xl font-semibold text-neutral-900">{result.passed ? 'Passed' : 'Not passed'}</h1>
      <p className="mt-3 text-5xl font-semibold text-brand-navy">{result.score_percent}%</p>
      <dl className="mt-6 grid grid-cols-3 gap-3 border-t border-neutral-200 pt-6 text-sm">
        <div><dt className="text-neutral-500">Attempts used</dt><dd className="font-semibold">{summary.attempts_used}</dd></div>
        <div><dt className="text-neutral-500">Attempts left</dt><dd className="font-semibold">{summary.attempts_remaining}</dd></div>
        <div><dt className="text-neutral-500">Best score</dt><dd className="font-semibold">{summary.best_score_percent ?? result.score_percent}%</dd></div>
      </dl>
      <p className="mt-5 text-sm text-neutral-500">Answer review is not available for Periodic Exams.</p>
      <Link to="/periodic-exam" className="mt-6 inline-flex rounded-md bg-brand-navy px-4 py-2 text-sm font-medium text-white hover:bg-brand-navy-light">
        Back to Periodic Exam
      </Link>
    </Card>
  )
}
