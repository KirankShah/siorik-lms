import { Suspense, lazy } from 'react'
import { Link, useParams } from 'react-router-dom'

// BlockNote adds a sizable chunk to the bundle — load it only when an
// instructor actually opens a page editor, not on every app load.
const PageEditor = lazy(() => import('../../components/admin/PageEditor').then((m) => ({ default: m.PageEditor })))

export function PageEditorPage() {
  const { pageId } = useParams<{ pageId: string }>()

  if (!pageId || Number.isNaN(Number(pageId))) {
    return <p className="text-sm text-red-600">Invalid page.</p>
  }

  return (
    <div className="space-y-4">
      <Link to="/admin/courses" className="text-sm text-slate-600 hover:underline">
        ← Back to courses
      </Link>
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <Suspense fallback={<p className="text-sm text-slate-500">Loading editor…</p>}>
          <PageEditor pageId={Number(pageId)} />
        </Suspense>
      </div>
    </div>
  )
}
