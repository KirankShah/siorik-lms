import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Clock3 } from 'lucide-react'
import { Card } from './ui/Card'
import { usePeriodicExamAvailability } from '../context/usePeriodicExamAvailability'
import { fetchPeriodicExamSummary } from '../lib/periodicExamsApi'
import {
  formatPeriodicExamDate,
  periodicExamErrorMessage,
  periodicExamNotOpenMessage,
  periodicExamReasonMessage,
  periodicExamStatus,
} from '../lib/periodicExamPresentation'
import type { PeriodicExamLearnerSummary } from '../types/periodicExams'

export function PeriodicExamDashboardCard() {
  const { availability, isLoading: availabilityLoading } = usePeriodicExamAvailability()
  const [summary, setSummary] = useState<PeriodicExamLearnerSummary | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const hasCycle = !!availability?.current_cycle

  useEffect(() => {
    if (!availability?.enabled || !hasCycle) return
    let cancelled = false
    fetchPeriodicExamSummary()
      .then((value) => {
        if (!cancelled) setSummary(value)
      })
      .catch((reason: unknown) => {
        if (!cancelled) setFailure(periodicExamErrorMessage(reason))
      })
    return () => {
      cancelled = true
    }
  }, [availability?.enabled, hasCycle])

  if (availabilityLoading || !availability?.enabled) return null

  const resultId = summary?.last_completed_attempt_id
  const action = summary?.open_attempt_id
    ? { label: 'Resume', to: `/periodic-exam/attempt/${summary.open_attempt_id}` }
    : summary?.passed && resultId
      ? { label: 'View result', to: `/periodic-exam/attempt/${resultId}/result` }
      : { label: 'Start', to: '/periodic-exam' }

  return (
    <Card data-testid="periodic-exam-dashboard-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-wide text-brand-gold uppercase">Periodic Exam</p>
          <h2 className="mt-1 text-lg font-semibold text-neutral-900">
            {summary?.cycle.display_label
              ?? availability.current_cycle?.display_label
              ?? availability.upcoming_cycle?.display_label
              ?? 'Current cycle'}
          </h2>
        </div>
        <Clock3 className="h-6 w-6 text-brand-navy" />
      </div>

      {!hasCycle ? (
        <p className="mt-4 text-sm text-neutral-600">{periodicExamNotOpenMessage(availability)}</p>
      ) : failure ? (
        <p className="mt-4 text-sm text-amber-700">{failure}</p>
      ) : !summary ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : (
        <>
          <p className="mt-3 text-sm text-neutral-600">
            {formatPeriodicExamDate(summary.cycle.starts_at)} – {formatPeriodicExamDate(summary.cycle.ends_at)}
          </p>
          <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
            <div><dt className="text-neutral-500">Status</dt><dd className="font-medium text-neutral-900">{periodicExamStatus(summary)}</dd></div>
            <div><dt className="text-neutral-500">Attempts left</dt><dd className="font-medium text-neutral-900">{summary.attempts_remaining}</dd></div>
            <div><dt className="text-neutral-500">Best score</dt><dd className="font-medium text-neutral-900">{summary.best_score_percent == null ? '—' : `${summary.best_score_percent}%`}</dd></div>
          </dl>
          {!summary.can_start && !summary.open_attempt_id && (
            <p className="mt-3 text-sm text-amber-700">{periodicExamReasonMessage(summary.reason_code)}</p>
          )}
          <Link
            to={action.to}
            className="mt-4 inline-flex rounded-md bg-brand-navy px-4 py-2 text-sm font-medium text-white hover:bg-brand-navy-light"
          >
            {action.label}
          </Link>
        </>
      )}
    </Card>
  )
}
