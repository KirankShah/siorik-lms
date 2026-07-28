import { useState } from 'react'
import type { FormEvent } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { updateCourse } from '../../lib/coursesApi'
import type { CourseDashboardContext } from './CourseDashboardLayout'

export function CourseCertificationTab() {
  const { course, reload } = useOutletContext<CourseDashboardContext>()
  const [passThreshold, setPassThreshold] = useState(course.certificate_pass_threshold)
  const [expiryMonths, setExpiryMonths] = useState(
    course.certificate_expiry_months === null ? '' : String(course.certificate_expiry_months),
  )
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setIsSaving(true)
    setError(null)
    setSuccess(false)
    try {
      await updateCourse(course.slug, {
        certificate_pass_threshold: passThreshold,
        certificate_expiry_months: expiryMonths === '' ? null : Number(expiryMonths),
      })
      reload()
      setSuccess(true)
    } catch {
      setError('Could not save certification settings.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold text-neutral-900">Certification</h2>
      <p className="mt-1 text-sm text-neutral-500">
        A learner earns a certificate once their enrollment is complete, every quiz in this course has been passed at
        least once, and the average of their best score per quiz meets the threshold below.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 max-w-sm space-y-4">
        <Input
          id="pass-threshold"
          label="Overall pass threshold (%)"
          type="number"
          min={0}
          max={100}
          required
          value={passThreshold}
          onChange={(e) => setPassThreshold(Number(e.target.value))}
        />

        <Input
          id="expiry-months"
          label="Expiry / refresher period (months)"
          type="number"
          min={1}
          placeholder="Never expires"
          value={expiryMonths}
          onChange={(e) => setExpiryMonths(e.target.value)}
        />
        <p className="-mt-2 text-xs text-neutral-400">Leave blank if certificates for this course never expire.</p>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {success && <p className="text-sm text-emerald-600">Saved.</p>}

        <Button type="submit" disabled={isSaving}>
          {isSaving ? 'Saving…' : 'Save certification settings'}
        </Button>
      </form>

      <div className="mt-8 border-t border-neutral-100 pt-6">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-neutral-900">Certificate template</h3>
          <Badge variant="gold">Coming soon</Badge>
        </div>
        <p className="mt-1 max-w-sm text-sm text-neutral-500">
          Every course currently uses the same certificate layout. Template selection will appear here once more than
          one design exists to choose from.
        </p>
      </div>
    </Card>
  )
}
