import { useEffect, useState } from 'react'
import { Check, Lock, Route as RouteIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { fetchMyLearningPath } from '../lib/learningPathApi'
import type { LearningPath, LearningPathCourse, LearningPathCourseState, LearningPathTier } from '../types/learningPath'

// This is the "what do I do next" view — a single sequential trail, distinct
// from the general course catalog (/courses) which stays for browsing
// everything available.

// Remembers each course's node state across loads (this browser tab only)
// purely so a course that just flipped current -> completed can get its
// one-shot completion flourish — see justCompletedIds below. Never used for
// anything else; an empty/missing cache (private window, cleared storage,
// first-ever visit) just means the flourish doesn't play, nothing else reads
// this.
const NODE_STATE_CACHE_KEY = 'learning-path-node-states-v1'

function readCachedNodeStates(): Record<number, LearningPathCourseState> {
  try {
    const raw = sessionStorage.getItem(NODE_STATE_CACHE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function writeCachedNodeStates(states: Record<number, LearningPathCourseState>) {
  try {
    sessionStorage.setItem(NODE_STATE_CACHE_KEY, JSON.stringify(states))
  } catch {
    // Best-effort only.
  }
}

function PathNode({
  course,
  isMilestoneTier,
  isJustCompleted,
}: {
  course: LearningPathCourse
  isMilestoneTier: boolean
  isJustCompleted: boolean
}) {
  if (course.state === 'completed') {
    return (
      <li className="relative flex items-start gap-4">
        <span
          className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
            isMilestoneTier ? 'bg-brand-gold text-brand-navy' : 'bg-teal-600 text-white'
          } ${isJustCompleted ? 'path-node-complete' : ''}`}
        >
          <Check className={`h-5 w-5 ${isJustCompleted ? 'path-node-checkmark' : ''}`} />
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

function TierGroup({ tier, justCompletedIds }: { tier: LearningPathTier; justCompletedIds: Set<number> }) {
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
          <PathNode
            key={course.id}
            course={course}
            isMilestoneTier={tier.is_complete}
            isJustCompleted={justCompletedIds.has(course.id)}
          />
        ))}
      </ul>
    </div>
  )
}

export function LearningPathSection() {
  const [path, setPath] = useState<LearningPath | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Node ids that transitioned current -> completed since this browser
  // tab's last load of the path — the subtle "felt, not announced" flourish
  // plays only for these, once, never on a plain revisit/refresh.
  const [justCompletedIds, setJustCompletedIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    let cancelled = false
    fetchMyLearningPath()
      .then((data) => {
        if (cancelled) return

        const previousStates = readCachedNodeStates()
        const nextStates: Record<number, LearningPathCourseState> = {}
        const newlyCompleted = new Set<number>()
        for (const tier of data.tiers) {
          for (const course of tier.courses) {
            if (previousStates[course.id] === 'current' && course.state === 'completed') {
              newlyCompleted.add(course.id)
            }
            nextStates[course.id] = course.state
          }
        }
        writeCachedNodeStates(nextStates)

        setJustCompletedIds(newlyCompleted)
        setPath(data)
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
                <TierGroup key={tier.tier_key} tier={tier} justCompletedIds={justCompletedIds} />
              ))}
            </div>
          </div>
        </>
      )}
    </Card>
  )
}
