import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card } from '../ui/Card'
import { cloneCourse } from '../../lib/coursesApi'
import type { Organization } from '../../types/auth'

interface CloneCoursePanelProps {
  courseSlug: string
  organizations: Organization[]
}

export function CloneCoursePanel({ courseSlug, organizations }: CloneCoursePanelProps) {
  const navigate = useNavigate()
  const [selectedOrgId, setSelectedOrgId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isCloning, setIsCloning] = useState(false)

  async function handleClone() {
    if (!selectedOrgId) return
    setIsCloning(true)
    setError(null)
    try {
      const cloned = await cloneCourse(courseSlug, Number(selectedOrgId))
      navigate(`/admin/courses/${cloned.slug}`)
    } catch {
      setError('Could not clone this course.')
      setIsCloning(false)
    }
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold text-neutral-900">Clone into an organization</h2>
      <p className="mt-1 text-xs text-neutral-500">
        Creates a brand new, independent copy of this course owned by the chosen organization — they can freely
        edit it (slides, quizzes, assignments, scenarios) without touching this platform course. Replaces any
        existing view-only access grant for that organization.
      </p>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <div className="mt-3 flex items-center gap-2">
        <select
          value={selectedOrgId}
          onChange={(e) => setSelectedOrgId(e.target.value)}
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        >
          <option value="">Select an organization…</option>
          {organizations.map((org) => (
            <option key={org.id} value={org.id}>
              {org.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!selectedOrgId || isCloning}
          onClick={handleClone}
          className="text-sm font-medium text-brand-navy disabled:opacity-60"
        >
          {isCloning ? 'Cloning…' : 'Clone into organization'}
        </button>
      </div>
    </Card>
  )
}
