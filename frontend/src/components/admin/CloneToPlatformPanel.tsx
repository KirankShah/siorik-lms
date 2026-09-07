import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card } from '../ui/Card'
import { cloneCourse } from '../../lib/coursesApi'

interface CloneToPlatformPanelProps {
  courseSlug: string
}

export function CloneToPlatformPanel({ courseSlug }: CloneToPlatformPanelProps) {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [isCloning, setIsCloning] = useState(false)

  async function handleClone() {
    setIsCloning(true)
    setError(null)
    try {
      const cloned = await cloneCourse(courseSlug)
      navigate(`/admin/courses/${cloned.slug}`)
    } catch {
      setError('Could not clone this course.')
      setIsCloning(false)
    }
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold text-neutral-900">Clone into the platform library</h2>
      <p className="mt-1 text-xs text-neutral-500">
        Creates a brand new, independent platform-owned copy of this organization course — editable by the
        platform team and shareable with any organization, without touching this original.
      </p>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <div className="mt-3">
        <button
          type="button"
          disabled={isCloning}
          onClick={handleClone}
          className="text-sm font-medium text-brand-navy disabled:opacity-60"
        >
          {isCloning ? 'Cloning…' : 'Clone into platform library'}
        </button>
      </div>
    </Card>
  )
}
