import { Suspense, lazy } from 'react'
import type { Enrollment, PageProgress, PageSummary } from '../../types/courses'
import { QuizPagePlayer } from './QuizPagePlayer'

// BlockNote adds a sizable chunk to the bundle — load it only once a learner
// actually opens a page that needs it, not on every course visit.
const ContentPagePlayer = lazy(() => import('./ContentPagePlayer').then((m) => ({ default: m.ContentPagePlayer })))
const AssignmentPagePlayer = lazy(() => import('./AssignmentPagePlayer').then((m) => ({ default: m.AssignmentPagePlayer })))

interface PagePlayerProps {
  page: PageSummary
  courseId: number
  enrollmentId: number
  existingProgress: PageProgress | undefined
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  onProgressSynced: (enrollment: Enrollment) => void
}

// Branches to the right read-only player for a page's type. Keyed by
// page.id at the call site so each page gets a fresh dwell timer / editor.
export function PagePlayer({
  page,
  courseId,
  enrollmentId,
  existingProgress,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onProgressSynced,
}: PagePlayerProps) {
  if (page.page_type === 'QUIZ') {
    return (
      <QuizPagePlayer
        page={page}
        courseId={courseId}
        enrollmentId={enrollmentId}
        existingProgress={existingProgress}
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        onPrevious={onPrevious}
        onNext={onNext}
        onProgressSynced={onProgressSynced}
      />
    )
  }

  if (page.page_type === 'ASSIGNMENT') {
    return (
      <Suspense fallback={<p className="text-sm text-slate-500">Loading assignment…</p>}>
        <AssignmentPagePlayer
          page={page}
          enrollmentId={enrollmentId}
          existingProgress={existingProgress}
          hasPrevious={hasPrevious}
          hasNext={hasNext}
          onPrevious={onPrevious}
          onNext={onNext}
          onProgressSynced={onProgressSynced}
        />
      </Suspense>
    )
  }

  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading page…</p>}>
      <ContentPagePlayer
        page={page}
        enrollmentId={enrollmentId}
        existingProgress={existingProgress}
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        onPrevious={onPrevious}
        onNext={onNext}
        onProgressSynced={onProgressSynced}
      />
    </Suspense>
  )
}
