import { useEffect, useState } from 'react'
import { Check, ChevronRight, ClipboardList, FileText, GitBranch, HelpCircle, Lock } from 'lucide-react'
import { Card } from '../ui/Card'
import { ProgressBar } from '../ProgressBar'
import type { FlatSlideEntry } from '../../lib/slideSequence'
import type { CourseDetail, Enrollment } from '../../types/courses'
import type { SlideType } from '../../types/slides'

const SLIDE_TYPE_ICON: Record<SlideType, typeof FileText> = {
  CONTENT: FileText,
  QUIZ: HelpCircle,
  ASSIGNMENT: ClipboardList,
  SCENARIO: GitBranch,
}

interface CourseSidebarProps {
  course: CourseDetail
  entries: FlatSlideEntry[]
  enrollment: Enrollment | null
  activeSlideId: number | null
  reachedSlideIds: Set<number>
  onSelectSlide: (slideId: number) => void
}

export function CourseSidebar({ course, entries, enrollment, activeSlideId, reachedSlideIds, onSelectSlide }: CourseSidebarProps) {
  const completedSlideIds = new Set(enrollment?.slide_progress.filter((p) => p.completed_at).map((p) => p.slide) ?? [])
  const totalSlides = entries.length
  const completedCount = entries.filter((e) => completedSlideIds.has(e.slide.id)).length

  const activeEntry = entries.find((e) => e.slide.id === activeSlideId)

  const [openModuleIds, setOpenModuleIds] = useState<Set<number>>(() => new Set(activeEntry ? [activeEntry.module.id] : []))
  const [openLessonIds, setOpenLessonIds] = useState<Set<number>>(() => new Set(activeEntry ? [activeEntry.lesson.id] : []))

  // Whichever module/lesson holds the current slide starts (and stays)
  // expanded as the learner advances — every other section is left as the
  // learner last set it, defaulting to collapsed.
  useEffect(() => {
    if (!activeEntry) return
    setOpenModuleIds((prev) => (prev.has(activeEntry.module.id) ? prev : new Set(prev).add(activeEntry.module.id)))
    setOpenLessonIds((prev) => (prev.has(activeEntry.lesson.id) ? prev : new Set(prev).add(activeEntry.lesson.id)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeEntry?.module.id, activeEntry?.lesson.id])

  function toggleModule(moduleId: number) {
    setOpenModuleIds((prev) => {
      const next = new Set(prev)
      if (next.has(moduleId)) next.delete(moduleId)
      else next.add(moduleId)
      return next
    })
  }

  function toggleLesson(lessonId: number) {
    setOpenLessonIds((prev) => {
      const next = new Set(prev)
      if (next.has(lessonId)) next.delete(lessonId)
      else next.add(lessonId)
      return next
    })
  }

  return (
    <Card className="no-print">
      <h1 className="text-sm font-semibold text-neutral-900">{course.title}</h1>
      <div className="mt-4 mb-1">
        <ProgressBar percent={enrollment?.progress_percent ?? 0} label="Course progress" />
        <p className="mt-1.5 text-xs text-neutral-400">
          {completedCount} of {totalSlides} slides complete
        </p>
      </div>

      <nav className="mt-5 space-y-1">
        {[...course.modules].sort((a, b) => a.order - b.order).map((courseModule) => {
          const moduleOpen = openModuleIds.has(courseModule.id)
          const moduleSlideIds = courseModule.lessons.flatMap((l) => l.slides.map((s) => s.id))
          const moduleCompleted = moduleSlideIds.filter((id) => completedSlideIds.has(id)).length

          return (
            <div key={courseModule.id} className="border-b border-neutral-100 pb-1 last:border-0">
              <button
                type="button"
                onClick={() => toggleModule(courseModule.id)}
                className="flex w-full items-center justify-between gap-2 rounded-md px-1 py-1.5 text-left transition hover:bg-neutral-50"
              >
                <span className="flex items-center gap-1.5">
                  <ChevronRight
                    className={`h-3.5 w-3.5 shrink-0 text-neutral-400 transition-transform ${moduleOpen ? 'rotate-90' : ''}`}
                  />
                  <span className="text-xs font-semibold tracking-wide text-neutral-500 uppercase">{courseModule.title}</span>
                </span>
                <span className="text-[11px] font-normal text-neutral-400">
                  {moduleCompleted}/{moduleSlideIds.length}
                </span>
              </button>

              {moduleOpen && (
                <div className="mt-0.5 space-y-0.5 pl-2">
                  {[...courseModule.lessons].sort((a, b) => a.order - b.order).map((lesson) => {
                    const sortedSlides = [...lesson.slides].sort((a, b) => a.order - b.order)
                    const lessonCompleted = sortedSlides.filter((s) => completedSlideIds.has(s.id)).length
                    const lessonOpen = openLessonIds.has(lesson.id)

                    if (lesson.is_locked) {
                      return (
                        <div key={lesson.id} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left">
                          <Lock className="h-3.5 w-3.5 shrink-0 text-neutral-300" />
                          <span className="flex-1 text-xs font-medium text-neutral-400">{lesson.title}</span>
                          <span className="shrink-0 text-[11px] text-neutral-300">Not in demo</span>
                        </div>
                      )
                    }

                    return (
                      <div key={lesson.id}>
                        <button
                          type="button"
                          onClick={() => toggleLesson(lesson.id)}
                          className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left transition hover:bg-neutral-50"
                        >
                          <span className="flex items-center gap-1.5 text-xs font-medium text-neutral-600">
                            <ChevronRight
                              className={`h-3.5 w-3.5 shrink-0 text-neutral-400 transition-transform ${lessonOpen ? 'rotate-90' : ''}`}
                            />
                            {lesson.title}
                          </span>
                          <span className="shrink-0 text-[11px] text-neutral-400">
                            ({lessonCompleted}/{sortedSlides.length})
                          </span>
                        </button>

                        {lessonOpen && (
                          <ul className="mt-0.5 space-y-0.5 pl-2">
                            {sortedSlides.map((slide) => {
                              const isComplete = completedSlideIds.has(slide.id)
                              const isActive = slide.id === activeSlideId
                              const isReached = reachedSlideIds.has(slide.id)
                              const SlideIcon = SLIDE_TYPE_ICON[slide.slide_type]

                              return (
                                <li key={slide.id}>
                                  <button
                                    type="button"
                                    disabled={!isReached}
                                    onClick={() => onSelectSlide(slide.id)}
                                    className={`relative flex w-full items-center gap-2 rounded-md py-1.5 pr-2 pl-3 text-left text-sm transition disabled:cursor-not-allowed ${
                                      isActive
                                        ? 'bg-brand-navy/8 font-medium text-brand-navy'
                                        : isReached
                                          ? 'text-neutral-600 hover:bg-neutral-50'
                                          : 'text-neutral-300'
                                    }`}
                                  >
                                    {isActive && <span className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-brand-navy" />}
                                    <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                                      {isComplete ? (
                                        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-brand-navy">
                                          <Check className="h-2.5 w-2.5 text-white" strokeWidth={3} />
                                        </span>
                                      ) : (
                                        <span className="h-1.5 w-1.5 rounded-full border border-neutral-300" />
                                      )}
                                    </span>
                                    <span className="shrink-0 text-neutral-400">
                                      {isReached ? <SlideIcon className="h-4 w-4" /> : <Lock className="h-4 w-4 text-neutral-300" />}
                                    </span>
                                    <span className="line-clamp-1">{slide.title || `Slide ${slide.order}`}</span>
                                  </button>
                                </li>
                              )
                            })}
                          </ul>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </Card>
  )
}
