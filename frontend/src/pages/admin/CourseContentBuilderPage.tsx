import { Suspense, lazy, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { LessonTree } from '../../components/admin/LessonTree'
import { fetchCourseDetail } from '../../lib/coursesApi'
import type { CourseDetail } from '../../types/courses'

// BlockNote adds a sizable chunk to the bundle — load it only once an
// instructor actually selects a page, not on every visit to this screen.
const PageEditor = lazy(() => import('../../components/admin/PageEditor').then((m) => ({ default: m.PageEditor })))

export function CourseContentBuilderPage() {
  const { slug } = useParams<{ slug: string }>()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedPageId, setSelectedPageId] = useState<number | null>(null)

  function loadCourse() {
    if (!slug) return
    fetchCourseDetail(slug)
      .then(setCourse)
      .catch(() => setLoadError('Could not load this course.'))
  }

  useEffect(loadCourse, [slug])

  if (loadError) return <p className="text-sm text-red-600">{loadError}</p>
  if (!course) return <p className="text-sm text-slate-500">Loading course…</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to={`/admin/courses/${course.slug}/edit`} className="text-sm text-slate-600 hover:underline">
            ← Back to course details
          </Link>
          <h1 className="mt-1 text-lg font-semibold text-slate-900">{course.title} — Content</h1>
        </div>
      </div>

      <div className="grid grid-cols-[280px_1fr] gap-4">
        <aside className="max-h-[calc(100vh-160px)] overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
          <LessonTree course={course} selectedPageId={selectedPageId} onSelectPage={setSelectedPageId} onChanged={loadCourse} />
        </aside>

        <main className="min-h-[calc(100vh-160px)] rounded-xl border border-slate-200 bg-white p-4">
          {selectedPageId ? (
            <Suspense fallback={<p className="text-sm text-slate-500">Loading editor…</p>}>
              <PageEditor pageId={selectedPageId} />
            </Suspense>
          ) : (
            <p className="text-sm text-slate-400">Select a page on the left, or add one to a lesson.</p>
          )}
        </main>
      </div>
    </div>
  )
}
