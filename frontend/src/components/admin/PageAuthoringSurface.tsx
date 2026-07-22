import { Suspense, lazy, useEffect, useState } from 'react'
import { fetchPage } from '../../lib/pagesApi'
import type { PageDetail } from '../../types/courses'
import { QuizAuthoringPanel } from './QuizAuthoringPanel'

// BlockNote adds a sizable chunk to the bundle — load it only once an
// instructor actually opens a page that needs it, not on every visit here.
const PageEditor = lazy(() => import('./PageEditor').then((m) => ({ default: m.PageEditor })))
const AssignmentAuthoringPanel = lazy(() => import('./AssignmentAuthoringPanel').then((m) => ({ default: m.AssignmentAuthoringPanel })))

interface PageAuthoringSurfaceProps {
  pageId: number
}

// Branches to the right authoring UI for a page's type. Used by the
// standalone /admin/pages/:pageId deep link; CourseContentBuilderPage
// branches inline instead since it already has the page's type from the
// lesson tree and would otherwise re-fetch it needlessly.
export function PageAuthoringSurface({ pageId }: PageAuthoringSurfaceProps) {
  const [page, setPage] = useState<PageDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setPage(null)
    setError(null)
    fetchPage(pageId)
      .then(setPage)
      .catch(() => setError('Could not load this page.'))
  }, [pageId])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!page) return <p className="text-sm text-slate-500">Loading page…</p>

  if (page.page_type === 'QUIZ') return <QuizAuthoringPanel pageId={page.id} pageTitle={page.title} />

  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Loading editor…</p>}>
      {page.page_type === 'ASSIGNMENT' ? <AssignmentAuthoringPanel pageId={page.id} /> : <PageEditor pageId={page.id} />}
    </Suspense>
  )
}
