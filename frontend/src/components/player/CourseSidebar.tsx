import { ProgressBar } from '../ProgressBar'
import type { CourseDetail, Enrollment, PageType } from '../../types/courses'
import type { FlatPageEntry } from '../../lib/pageSequence'

const PAGE_TYPE_ICON: Record<PageType, string> = {
  CONTENT: '📄',
  QUIZ: '❓',
  ASSIGNMENT: '📋',
}

interface CourseSidebarProps {
  course: CourseDetail
  entries: FlatPageEntry[]
  enrollment: Enrollment | null
  activePageId: number | null
  unlockedPageIds: Set<number>
  onSelectPage: (pageId: number) => void
}

export function CourseSidebar({ course, entries, enrollment, activePageId, unlockedPageIds, onSelectPage }: CourseSidebarProps) {
  const completedPageIds = new Set(enrollment?.page_progress.filter((p) => p.completed_at).map((p) => p.page) ?? [])
  const totalPages = entries.length
  const completedCount = entries.filter((e) => completedPageIds.has(e.page.id)).length

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h1 className="text-sm font-semibold text-slate-900">{course.title}</h1>
      <div className="mt-3">
        <ProgressBar percent={enrollment?.progress_percent ?? 0} label="Course progress" />
        <p className="mt-1 text-xs text-slate-400">
          {completedCount} of {totalPages} pages complete
        </p>
      </div>

      <nav className="mt-4 space-y-4">
        {course.modules.map((courseModule) => (
          <div key={courseModule.id}>
            <p className="mb-1 text-xs font-semibold tracking-wide text-slate-400 uppercase">{courseModule.title}</p>
            <div className="space-y-3">
              {courseModule.lessons.map((lesson) => {
                const lessonCompleted = lesson.pages.filter((p) => completedPageIds.has(p.id)).length
                return (
                  <div key={lesson.id}>
                    <p className="mb-0.5 text-xs font-medium text-slate-600">
                      {lesson.title}{' '}
                      <span className="text-slate-400">
                        ({lessonCompleted}/{lesson.pages.length})
                      </span>
                    </p>
                    <ul className="space-y-0.5">
                      {lesson.pages.map((page) => {
                        const isComplete = completedPageIds.has(page.id)
                        const isActive = page.id === activePageId
                        const isUnlocked = unlockedPageIds.has(page.id)
                        return (
                          <li key={page.id}>
                            <button
                              type="button"
                              disabled={!isUnlocked}
                              onClick={() => onSelectPage(page.id)}
                              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition disabled:cursor-not-allowed disabled:text-slate-300 ${
                                isActive ? 'bg-slate-100 text-slate-900' : isUnlocked ? 'text-slate-600 hover:bg-slate-50' : ''
                              }`}
                            >
                              <span
                                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] ${
                                  isComplete ? 'bg-emerald-500 text-white' : 'border border-slate-300'
                                }`}
                              >
                                {isComplete && '✓'}
                              </span>
                              <span className="shrink-0">{isUnlocked ? PAGE_TYPE_ICON[page.page_type] : '🔒'}</span>
                              <span className="line-clamp-1">{page.title}</span>
                            </button>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
    </div>
  )
}
