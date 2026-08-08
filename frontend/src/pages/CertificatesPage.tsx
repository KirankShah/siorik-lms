import { useEffect, useState } from 'react'
import { Award, Download } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { downloadCertificate, fetchCertificates } from '../lib/certificatesApi'
import type { Certificate } from '../types/certificates'

function CertificateCard({ certificate }: { certificate: Certificate }) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleDownload() {
    setIsDownloading(true)
    setError(null)
    try {
      await downloadCertificate(certificate.id, `${certificate.certificate_number}.pdf`)
    } catch {
      setError('Could not download the certificate.')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <Card className="flex flex-col items-center gap-3 p-6 text-center transition-transform duration-200 hover:scale-105">
      <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-brand-gold/30 to-brand-gold/10 shadow-[0_0_24px_rgba(233,183,48,0.45)] ring-1 ring-brand-gold/40">
        <Award className="h-7 w-7 text-brand-gold" />
      </div>

      <div>
        <p className="text-sm font-semibold text-neutral-900">{certificate.course_title}</p>
        <p className="mt-1 text-xs text-neutral-500">Issued {new Date(certificate.issued_at).toLocaleDateString()}</p>
        <p className="mt-1 font-mono text-[11px] text-neutral-400">{certificate.certificate_number}</p>
      </div>

      <Button size="sm" onClick={handleDownload} disabled={isDownloading} className="mt-1">
        <Download className="h-3.5 w-3.5" />
        {isDownloading ? 'Preparing…' : 'Download'}
      </Button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </Card>
  )
}

export function CertificatesPage() {
  const [certificates, setCertificates] = useState<Certificate[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchCertificates()
      .then(setCertificates)
      .catch(() => setError('Could not load certificates.'))
  }, [])

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (!certificates) {
    return <p className="text-sm text-neutral-500">Loading certificates…</p>
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Certificates</h1>

      {certificates.length === 0 ? (
        <Card className="mt-6 flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-navy/10 text-brand-navy">
            <Award className="h-6 w-6" />
          </div>
          <p className="text-sm font-medium text-neutral-900">No certificates yet</p>
          <p className="max-w-sm text-sm text-neutral-500">
            Complete a course with a passing average and your certificate will appear here automatically.
          </p>
        </Card>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {certificates.map((certificate) => (
            <CertificateCard key={certificate.id} certificate={certificate} />
          ))}
        </div>
      )}
    </div>
  )
}
