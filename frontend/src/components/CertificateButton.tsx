import { useState } from 'react'
import { downloadCertificate, issueCertificate } from '../lib/certificatesApi'

interface CertificateButtonProps {
  // Fired only after a successful download (never on error, so a failed
  // attempt leaves the learner on the button to retry rather than getting
  // swept away by the caller's post-download navigation).
  onDownloaded?: () => void
}

// Only ever rendered once the caller has confirmed this is the learner's
// Learning Path finale (see CourseCompletionModal) — there's exactly one
// certificate per learner, so no course to identify it by.
export function CertificateButton({ onDownloaded }: CertificateButtonProps) {
  const [certificateId, setCertificateId] = useState<number | null>(null)
  const [isPreparing, setIsPreparing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    setIsPreparing(true)
    setError(null)
    try {
      if (!certificateId) {
        const certificate = await issueCertificate()
        setCertificateId(certificate.id)
        await downloadCertificate(certificate.id, `${certificate.certificate_number}.pdf`)
      } else {
        await downloadCertificate(certificateId, 'certificate.pdf')
      }
      onDownloaded?.()
    } catch {
      setError('Could not generate the certificate. Please try again.')
    } finally {
      setIsPreparing(false)
    }
  }

  return (
    <div>
      <button
        type="button"
        disabled={isPreparing}
        onClick={handleClick}
        className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPreparing ? 'Preparing…' : 'Download Certificate'}
      </button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}
