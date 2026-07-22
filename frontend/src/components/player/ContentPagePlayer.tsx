import { useCallback, useEffect, useRef, useState } from 'react'
import { useCreateBlockNote } from '@blocknote/react'
import { BlockNoteView } from '@blocknote/mantine'
import '@blocknote/core/fonts/inter.css'
import '@blocknote/mantine/style.css'
import { schema } from '../../lib/blocknote/schema'
import { savePageProgress } from '../../lib/coursesApi'
import { fetchPage } from '../../lib/pagesApi'
import type { Enrollment, PageDetail, PageProgress, PageSummary } from '../../types/courses'
import { PageNavFooter } from './PageNavFooter'

const SYNC_INTERVAL_MS = 10_000

interface ContentPagePlayerProps {
  page: PageSummary
  enrollmentId: number
  existingProgress: PageProgress | undefined
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  onProgressSynced: (enrollment: Enrollment) => void
}

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export function ContentPagePlayer({
  page,
  enrollmentId,
  existingProgress,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onProgressSynced,
}: ContentPagePlayerProps) {
  const [pageDetail, setPageDetail] = useState<PageDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    fetchPage(page.id)
      .then(setPageDetail)
      .catch(() => setLoadError('Could not load this page.'))
  }, [page.id])

  if (loadError) return <p className="text-sm text-red-600">{loadError}</p>
  if (!pageDetail) return <p className="text-sm text-slate-500">Loading page…</p>

  return (
    <ContentPagePlayerLoaded
      pageDetail={pageDetail}
      estimatedMinutes={page.estimated_minutes}
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

function ContentPagePlayerLoaded({
  pageDetail,
  estimatedMinutes,
  enrollmentId,
  existingProgress,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onProgressSynced,
}: {
  pageDetail: PageDetail
  estimatedMinutes: number
  enrollmentId: number
  existingProgress: PageProgress | undefined
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  onProgressSynced: (enrollment: Enrollment) => void
}) {
  const editor = useCreateBlockNote({
    schema,
    initialContent: pageDetail.content_json.length > 0 ? (pageDetail.content_json as never) : undefined,
  })

  const alreadyComplete = existingProgress?.completed_at != null
  const baseTimeSpent = existingProgress?.time_spent_seconds ?? 0
  const requiredSeconds = estimatedMinutes * 60

  const [sessionElapsed, setSessionElapsed] = useState(0)
  const [isAdvancing, setIsAdvancing] = useState(false)
  const unsyncedSecondsRef = useRef(0)
  const isPausedRef = useRef(false)

  const syncProgress = useCallback(
    async (completed: boolean) => {
      const delta = unsyncedSecondsRef.current
      unsyncedSecondsRef.current = 0
      if (delta === 0 && !completed) return
      const enrollment = await savePageProgress(enrollmentId, {
        page: pageDetail.id,
        time_spent_seconds: delta,
        completed,
      })
      onProgressSynced(enrollment)
    },
    [enrollmentId, pageDetail.id, onProgressSynced],
  )

  // Pause the dwell clock when the tab isn't visible — time "spent" on a
  // page a student has switched away from shouldn't count toward unlocking Next.
  useEffect(() => {
    function handleVisibility() {
      isPausedRef.current = document.hidden
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [])

  useEffect(() => {
    if (alreadyComplete) return
    const tick = setInterval(() => {
      if (isPausedRef.current) return
      setSessionElapsed((s) => s + 1)
      unsyncedSecondsRef.current += 1
    }, 1000)
    return () => clearInterval(tick)
  }, [alreadyComplete])

  useEffect(() => {
    if (alreadyComplete) return
    const heartbeat = setInterval(() => void syncProgress(false), SYNC_INTERVAL_MS)
    return () => {
      clearInterval(heartbeat)
      void syncProgress(false)
    }
  }, [alreadyComplete, syncProgress])

  const totalDwell = baseTimeSpent + sessionElapsed
  const canProceed = alreadyComplete || requiredSeconds === 0 || totalDwell >= requiredSeconds
  const remaining = Math.max(0, requiredSeconds - totalDwell)

  async function handleNext() {
    setIsAdvancing(true)
    try {
      await syncProgress(true)
    } finally {
      setIsAdvancing(false)
      onNext()
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">{pageDetail.title}</h2>
        <button
          type="button"
          onClick={() => window.print()}
          className="no-print rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          ⬇ Download as PDF
        </button>
      </div>

      <div className="print-target rounded-xl border border-slate-200 bg-white">
        <BlockNoteView editor={editor} editable={false} theme="light" />
      </div>

      <PageNavFooter
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        onPrevious={onPrevious}
        onNext={() => void handleNext()}
        nextDisabled={!canProceed || isAdvancing}
        nextDisabledReason={!canProceed ? `Keep reading — available in ${formatCountdown(remaining)}` : undefined}
      />
    </div>
  )
}
