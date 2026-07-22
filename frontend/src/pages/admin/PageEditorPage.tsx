import { Link, useParams } from 'react-router-dom'
import { PageAuthoringSurface } from '../../components/admin/PageAuthoringSurface'

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
        <PageAuthoringSurface pageId={Number(pageId)} />
      </div>
    </div>
  )
}
