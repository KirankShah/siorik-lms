import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import {
  fetchDemoLessonAccess,
  grantDemoLessonAccess,
  revokeDemoLessonAccess,
  updateCourse,
} from '../../lib/coursesApi'
import type { CourseDashboardContext } from './CourseDashboardLayout'

export function CourseDemoAccessTab() {
  const { course, reload } = useOutletContext<CourseDashboardContext>()

  const [isDemoAvailable, setIsDemoAvailable] = useState(course.is_demo_available)
  const [isSavingToggle, setIsSavingToggle] = useState(false)
  const [toggleError, setToggleError] = useState<string | null>(null)

  const [grantedLessonIds, setGrantedLessonIds] = useState<Set<number>>(new Set())
  const [pendingLessonId, setPendingLessonId] = useState<number | null>(null)
  const [lessonError, setLessonError] = useState<string | null>(null)

  useEffect(() => {
    setIsDemoAvailable(course.is_demo_available)
  }, [course.is_demo_available])

  useEffect(() => {
    fetchDemoLessonAccess(course.slug)
      .then((grants) => setGrantedLessonIds(new Set(grants.map((g) => g.lesson))))
      .catch(() => {})
  }, [course.slug])

  async function handleToggleDemoAvailable() {
    const next = !isDemoAvailable
    setIsSavingToggle(true)
    setToggleError(null)
    try {
      await updateCourse(course.slug, { is_demo_available: next })
      setIsDemoAvailable(next)
      reload()
    } catch {
      setToggleError('Could not save this setting.')
    } finally {
      setIsSavingToggle(false)
    }
  }

  async function handleToggleLesson(lessonId: number, currentlyGranted: boolean) {
    setPendingLessonId(lessonId)
    setLessonError(null)
    try {
      if (currentlyGranted) {
        await revokeDemoLessonAccess(course.slug, lessonId)
        setGrantedLessonIds((prev) => {
          const next = new Set(prev)
          next.delete(lessonId)
          return next
        })
      } else {
        await grantDemoLessonAccess(course.slug, lessonId)
        setGrantedLessonIds((prev) => new Set(prev).add(lessonId))
      }
    } catch {
      setLessonError('Could not update this lesson.')
    } finally {
      setPendingLessonId(null)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-sm font-semibold text-neutral-900">Demo access</h2>
        <p className="mt-1 max-w-lg text-sm text-neutral-500">
          When enabled, demo users (accounts marked <code className="rounded bg-neutral-100 px-1 py-0.5">is_demo</code>)
          can only open the lessons checked below — every other lesson renders locked for them. Non-demo learners are
          never affected by this.
        </p>

        <label className="mt-4 flex items-center gap-2 text-sm text-neutral-700">
          <input
            type="checkbox"
            checked={isDemoAvailable}
            disabled={isSavingToggle}
            onChange={() => void handleToggleDemoAvailable()}
            className="h-4 w-4 rounded border-neutral-300"
          />
          Enable demo access for this course
        </label>
        {toggleError && <p className="mt-2 text-sm text-red-600">{toggleError}</p>}
      </Card>

      {isDemoAvailable && (
        <Card>
          <h2 className="text-sm font-semibold text-neutral-900">Lessons visible to demo users</h2>
          {lessonError && <p className="mt-2 text-sm text-red-600">{lessonError}</p>}

          <div className="mt-4 space-y-5">
            {[...course.modules].sort((a, b) => a.order - b.order).map((courseModule) => (
              <div key={courseModule.id}>
                <p className="text-xs font-semibold tracking-wide text-neutral-500 uppercase">{courseModule.title}</p>
                <ul className="mt-2 space-y-1.5">
                  {[...courseModule.lessons].sort((a, b) => a.order - b.order).map((lesson) => {
                    const granted = grantedLessonIds.has(lesson.id)
                    return (
                      <li key={lesson.id}>
                        <label className="flex items-center gap-2 text-sm text-neutral-700">
                          <input
                            type="checkbox"
                            checked={granted}
                            disabled={pendingLessonId === lesson.id}
                            onChange={() => void handleToggleLesson(lesson.id, granted)}
                            className="h-4 w-4 rounded border-neutral-300"
                          />
                          {lesson.title}
                        </label>
                      </li>
                    )
                  })}
                  {courseModule.lessons.length === 0 && (
                    <li className="text-sm text-neutral-400 italic">No lessons in this module.</li>
                  )}
                </ul>
              </div>
            ))}
            {course.modules.length === 0 && <p className="text-sm text-neutral-400">This course has no modules yet.</p>}
          </div>

          <div className="mt-4 border-t border-neutral-100 pt-3">
            <Button type="button" variant="ghost" size="sm" onClick={() => reload()}>
              Refresh
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
