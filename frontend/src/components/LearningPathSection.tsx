import { useEffect, useState } from 'react'
import { Check, Lock, Route as RouteIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { fetchMyLearningPath } from '../lib/learningPathApi'
import type { LearningPath, LearningPathCourse, LearningPathTier } from '../types/learningPath'

// This is the "what do I do next" view — a single sequential trail, distinct
// from the general course catalog (/courses) which stays for browsing
// everything available.

function PathNode({ course, isMilestoneTier }: { course: LearningPathCourse; isMilestoneTier: boolean }) {
  if (course.state === 'completed') {
    return (
      <li className="relative flex items-start gap-4">
        <span
          className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
            isMilestoneTier ? 'bg-brand-gold text-brand-navy' : 'bg-teal-600 text-white'
          }`}
        >
          <Check className="h-5 w-5" />
        </span>
        <div className="pt-2">
          <p className="text-sm font-medium text-neutral-900">{course.title}</p>
          <p className={`text-xs font-medium ${isMilestoneTier ? 'text-brand-gold' : 'text-teal-700'}`}>Completed</p>
        </div>
      </li>
    )
  }

  if (course.state === 'current') {
    return (
      <li className="relative flex items-start gap-4">
        <span className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-navy ring-4 ring-brand-navy/15">
          <span className="h-2.5 w-2.5 rounded-full bg-white" />
        </span>
        <div className="flex flex-1 flex-wrap items-center justify-between gap-3 pt-1.5">
          <p className="text-sm font-semibold text-neutral-900">{course.title}</p>
          <Link to={`/courses/${course.slug}`}>
            <Button size="sm">Continue</Button>
          </Link>
        </div>
      </li>
    )
  }

  return (
    <li className="relative flex items-start gap-4">
      <span className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-neutral-200 text-neutral-400">
        <Lock className="h-4 w-4" />
      </span>
      <div className="pt-2">
        <p className="text-sm font-medium text-neutral-400">{course.title}</p>
        <p className="text-xs text-neutral-400">Locked</p>
      </div>
    </li>
  )
}

function TierGroup({ tier }: { tier: LearningPathTier }) {
  return (
    <div>
      <p
        className={`mb-3 pl-14 text-xs font-semibold uppercase tracking-wide ${
          tier.is_complete ? 'text-brand-gold' : 'text-neutral-400'
        }`}
      >
        {tier.tier_label}
        {tier.is_complete ? ' — Completed' : ''}
      </p>
      <ul className="space-y-5">
        {tier.courses.map((course) => (
          <PathNode key={course.id} course={course} isMilestoneTier={tier.is_complete} />
        ))}
      </ul>
    </div>
  )
}

export function LearningPathSection() {
  const [path, setPath] = useState<LearningPath | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchMyLearningPath()
      .then((data) => {
        if (!cancelled) setPath(data)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your learning path.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Card className="p-6 sm:p-8">
      <div className="flex items-center gap-2.5">
        <RouteIcon className="h-5 w-5 text-brand-navy" />
        <h2 className="text-lg font-semibold text-neutral-900">My Learning Path</h2>
      </div>

      {error ? (
        <p className="mt-4 text-sm text-red-600">{error}</p>
      ) : !path ? (
        <p className="mt-4 text-sm text-neutral-500">Loading…</p>
      ) : path.tiers.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">No learning path has been assigned to you yet.</p>
      ) : (
        <>
          {path.branch_percentile !== null && (
            <p className="mt-3 text-sm text-neutral-500">
              You're ahead of <span className="font-semibold text-brand-navy">{path.branch_percentile}%</span> of
              your branch on this path.
            </p>
          )}

          <div className="relative mt-6">
            <div className="absolute bottom-2 left-[19px] top-2 w-0.5 bg-neutral-200" aria-hidden="true" />
            <div className="space-y-8">
              {path.tiers.map((tier) => (
                <TierGroup key={tier.tier_key} tier={tier} />
              ))}
            </div>
          </div>
        </>
      )}
    </Card>
  )
}
