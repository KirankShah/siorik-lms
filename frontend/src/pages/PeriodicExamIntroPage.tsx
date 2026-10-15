import { useEffect, useState } from 'react'
import { CheckCircle2, Clock3, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { usePeriodicExamAvailability } from '../context/usePeriodicExamAvailability'
import { fetchPeriodicExamSummary, startPeriodicExamAttempt } from '../lib/periodicExamsApi'
import { formatPeriodicExamDate, periodicExamReasonMessage } from '../lib/periodicExamPresentation'
import type { PeriodicExamLearnerSummary } from '../types/periodicExams'

export function PeriodicExamIntroPage() {
  const navigate = useNavigate()
  const { availability } = usePeriodicExamAvailability()
  const [summary, setSummary] = useState<PeriodicExamLearnerSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    fetchPeriodicExamSummary().then(setSummary).catch(() => setError('Periodic Exam details could not be loaded.'))
  }, [])

  const cycle = availability?.current_cycle

  async function start() {
    if (starting) return
    setStarting(true)
    setError(null)
    try {
      const attempt = await startPeriodicExamAttempt()
      navigate(`/periodic-exam/attempt/${attempt.id}`)
    } catch {
      setError('The attempt could not be started. Please try again.')
      setStarting(false)
    }
  }

  if (!summary || !cycle) {
    return <p className={error ? 'text-sm text-red-600' : 'text-sm text-neutral-500'}>{error ?? 'Loading Periodic Exam…'}</p>
  }

  const reason = periodicExamReasonMessage(summary.reason_code)
  const resultId = summary.last_completed_attempt_id

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="text-center">
        <p className="text-sm font-semibold tracking-wide text-brand-gold uppercase">Assigned to you</p>
        <h1 className="mt-2 text-3xl font-semibold text-brand-navy">Periodic Exam</h1>
        <p className="mt-3 text-neutral-600">
          {cycle.display_label} closes on {formatPeriodicExamDate(cycle.ends_at)}.
        </p>
      </div>

      <Card>
        <div className="grid gap-4 sm:grid-cols-4">
          <Metric label="Questions" value={String(cycle.questions_per_exam)} />
          <Metric label="Per question" value={`${cycle.seconds_per_question}s`} />
          <Metric label="Pass mark" value={`${cycle.pass_mark_percent}%`} />
          <Metric label="Attempts left" value={String(summary.attempts_remaining)} />
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-neutral-900">Before you begin</h2>
        <ul className="mt-4 space-y-4 text-sm text-neutral-700">
          <Rule icon={Clock3}>Each question has its own strict timer. It locks automatically when time expires.</Rule>
          <Rule icon={ShieldCheck}>Questions move forward only. You cannot return to an earlier question.</Rule>
          <Rule icon={CheckCircle2}>Passing any attempt clears this cycle; your best submitted score is kept.</Rule>
        </ul>
      </Card>

      {error && <p role="alert" className="text-center text-sm text-red-600">{error}</p>}
      {reason && !summary.open_attempt_id && <p className="text-center text-sm text-amber-700">{reason}</p>}

      <div className="flex justify-center">
        {summary.open_attempt_id ? (
          <Button onClick={() => navigate(`/periodic-exam/attempt/${summary.open_attempt_id}`)}>Resume exam</Button>
        ) : summary.can_start ? (
          <Button onClick={() => void start()} disabled={starting}>{starting ? 'Starting…' : 'Start exam'}</Button>
        ) : resultId ? (
          <Button onClick={() => navigate(`/periodic-exam/attempt/${resultId}/result`)}>View result</Button>
        ) : null}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-neutral-50 p-4 text-center"><p className="text-2xl font-semibold text-brand-navy">{value}</p><p className="mt-1 text-xs text-neutral-500">{label}</p></div>
}

function Rule({ icon: Icon, children }: { icon: typeof Clock3; children: string }) {
  return <li className="flex gap-3"><Icon className="mt-0.5 h-5 w-5 shrink-0 text-brand-navy" /><span>{children}</span></li>
}
