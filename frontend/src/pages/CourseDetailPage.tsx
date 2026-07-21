import { useParams } from 'react-router-dom'

export function CourseDetailPage() {
  const { id } = useParams<{ id: string }>()

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-lg font-semibold text-slate-900">Course {id}</h1>
      <p className="mt-2 text-sm text-slate-600">No content yet.</p>
    </div>
  )
}
