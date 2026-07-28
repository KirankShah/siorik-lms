import { useEffect, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { bulkEnroll, fetchCourses } from '../../lib/coursesApi'
import type { BulkEnrollResult } from '../../types/admin'
import type { CourseListItem } from '../../types/courses'

export function BulkEnrollPage() {
  const [courses, setCourses] = useState<CourseListItem[]>([])
  const [courseSlug, setCourseSlug] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<BulkEnrollResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    fetchCourses().then(setCourses).catch(() => {})
  }, [])

  async function handleSubmit() {
    if (!courseSlug || !file) return
    setIsSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const response = await bulkEnroll(courseSlug, file)
      setResult(response)
    } catch {
      setError('Could not process the CSV file.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Bulk Enroll</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Upload a CSV file with one email address per line (a header row is fine — anything without an "@" is skipped).
      </p>

      <Card className="mt-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700">Course</label>
          <select
            value={courseSlug}
            onChange={(e) => setCourseSlug(e.target.value)}
            className="mt-1 w-full max-w-sm rounded-md border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value="">Select a course…</option>
            {courses.map((course) => (
              <option key={course.id} value={course.slug}>
                {course.title}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-neutral-700">CSV file</label>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 text-sm"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Button disabled={!courseSlug || !file || isSubmitting} onClick={handleSubmit}>
          {isSubmitting ? 'Uploading…' : 'Enroll Learners'}
        </Button>
      </Card>

      {result && (
        <Card className="mt-4 space-y-3">
          <p className="text-sm text-emerald-700">
            Enrolled {result.enrolled.length} learner{result.enrolled.length === 1 ? '' : 's'}.
          </p>
          {result.already_enrolled.length > 0 && (
            <p className="text-sm text-neutral-500">
              Already enrolled ({result.already_enrolled.length}): {result.already_enrolled.join(', ')}
            </p>
          )}
          {result.not_found.length > 0 && (
            <p className="text-sm text-amber-700">
              No account found for ({result.not_found.length}): {result.not_found.join(', ')}
            </p>
          )}
        </Card>
      )}
    </div>
  )
}
