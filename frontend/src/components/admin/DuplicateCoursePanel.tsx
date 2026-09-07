import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card } from '../ui/Card'
import { duplicateCourse } from '../../lib/coursesApi'

interface DuplicateCoursePanelProps {
  courseSlug: string
}

export function DuplicateCoursePanel({ courseSlug }: DuplicateCoursePanelProps) {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [isDuplicating, setIsDuplicating] = useState(false)

  async function handleDuplicate() {
    setIsDuplicating(true)
    setError(null)
    try {
      const copy = await duplicateCourse(courseSlug)
      navigate(`/admin/courses/${copy.slug}`)
    } catch {
      setError('Could not duplicate this course.')
      setIsDuplicating(false)
    }
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold text-neutral-900">Duplicate this course</h2>
      <p className="mt-1 text-xs text-neutral-500">
        Creates a brand new, independent draft copy with the same owner as this course — its content
        (modules, lessons, pages, quizzes, assignments, scenarios) is copied, learner data is not. The
        copy's title gets a “(Copy)” suffix and it starts unpublished.
      </p>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <div className="mt-3">
        <button
          type="button"
          disabled={isDuplicating}
          onClick={handleDuplicate}
          className="text-sm font-medium text-brand-navy disabled:opacity-60"
        >
          {isDuplicating ? 'Duplicating…' : 'Duplicate course'}
        </button>
      </div>
    </Card>
  )
}
