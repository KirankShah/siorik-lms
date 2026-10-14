import { useEffect, useState } from 'react'
import { Award, Download, Search } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { useAuth } from '../context/AuthContext'
import { downloadAdminCertificatesZip, downloadBlob, downloadCertificate, fetchAdminCertificates, fetchCertificates } from '../lib/certificatesApi'
import type { AdminCertificate, Certificate } from '../types/certificates'

const ADMIN_PAGE_SIZE = 25

function CertificateCard({ certificate, isOrgAdmin = false }: { certificate: Certificate | AdminCertificate; isOrgAdmin?: boolean }) {
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
        {isOrgAdmin && 'staff_name' in certificate && (
          <>
            <p className="break-words text-base font-semibold text-neutral-900">{certificate.staff_name}</p>
            <p className="mt-1 break-words text-sm text-neutral-600">{certificate.staff_email}</p>
            <p className="mt-1 text-xs text-neutral-500">{certificate.level || 'Level not recorded'}</p>
          </>
        )}
        <p className="text-sm font-semibold text-neutral-900">{certificate.title}</p>
        <p className="mt-1 text-xs text-neutral-500">Issued {new Date(certificate.issued_at).toLocaleDateString()}</p>
        <p className="mt-1 font-mono text-[10px] text-neutral-400">{certificate.certificate_number}</p>
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
  const { user } = useAuth()
  const isOrgAdmin = user?.role === 'ORG_ADMIN'
  const [certificates, setCertificates] = useState<Array<Certificate | AdminCertificate> | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<'newest' | 'name'>('newest')
  const [page, setPage] = useState(1)
  const [isLoadingAdmin, setIsLoadingAdmin] = useState(false)
  const [isPreparingZip, setIsPreparingZip] = useState(false)
  const [zipStatus, setZipStatus] = useState<string | null>(null)
  const [zipError, setZipError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) return
    let active = true
    setError(null)
    if (!isOrgAdmin) {
      setIsLoadingAdmin(false)
      fetchCertificates()
        .then((items) => { if (active) { setCertificates(items); setTotalCount(items.length) } })
        .catch(() => { if (active) setError('Could not load certificates.') })
      return () => { active = false }
    }
    setIsLoadingAdmin(true)
    const timer = window.setTimeout(() => {
      fetchAdminCertificates({ search: search.trim(), sort, page })
        .then((data) => { if (active) { setCertificates(data.results); setTotalCount(data.count); setIsLoadingAdmin(false) } })
        .catch(() => { if (active) { setError('Could not load certificates.'); setIsLoadingAdmin(false) } })
    }, 250)
    return () => { active = false; window.clearTimeout(timer) }
  }, [isOrgAdmin, page, search, sort, user])

  async function handleDownloadAll() {
    const countAtStart = totalCount
    const partCount = Math.ceil(countAtStart / ADMIN_PAGE_SIZE)
    if (!countAtStart || !partCount) return
    setIsPreparingZip(true)
    setZipError(null)
    try {
      for (let part = 1; part <= partCount; part += 1) {
        setZipStatus(`Preparing ZIP ${part} of ${partCount}…`)
        const blob = await downloadAdminCertificatesZip(search.trim(), sort, part)
        const filename = partCount === 1
          ? 'certificates.zip'
          : `certificates-part-${part}-of-${partCount}.zip`
        downloadBlob(blob, filename)
      }
      setZipStatus(partCount === 1 ? 'Download ready.' : `Downloaded ${partCount} ZIP parts.`)
    } catch {
      setZipError('Could not prepare the certificate ZIP. Please try again.')
      setZipStatus(null)
    } finally {
      setIsPreparingZip(false)
    }
  }

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }

  if (!certificates) {
    return <p className="text-sm text-neutral-500">Loading certificates…</p>
  }

  return (
    <div>
      <h1 className="text-lg font-semibold text-neutral-900">Certificates</h1>

      {isOrgAdmin && (
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="min-w-60 flex-1">
            <span className="sr-only">Search staff name or email</span>
            <span className="flex items-center gap-2 rounded-md border border-neutral-300 px-3 py-2">
              <Search className="h-4 w-4 text-neutral-400" />
              <input
                aria-label="Search staff name or email"
                className="w-full bg-transparent text-sm outline-none"
                placeholder="Search staff name or email"
                value={search}
                onChange={(event) => { setSearch(event.target.value); setPage(1) }}
              />
            </span>
          </label>
          <label className="text-sm text-neutral-600">
            Sort
            <select aria-label="Sort certificates" className="ml-2 rounded-md border border-neutral-300 bg-white px-2 py-2" value={sort} onChange={(event) => { setSort(event.target.value as 'newest' | 'name'); setPage(1) }}>
              <option value="newest">Newest first</option>
              <option value="name">Name A–Z</option>
            </select>
          </label>
          <Button size="sm" onClick={handleDownloadAll} disabled={isPreparingZip || isLoadingAdmin || totalCount === 0}>
            <Download className="h-3.5 w-3.5" />
            {isPreparingZip ? 'Preparing…' : `Download all (${totalCount})`}
          </Button>
          {zipStatus && <p role="status" className="w-full text-sm text-neutral-600">{zipStatus}</p>}
          {zipError && <p role="alert" className="w-full text-sm text-red-600">{zipError}</p>}
        </div>
      )}

      {certificates.length === 0 ? (
        <Card className="mt-6 flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-navy/10 text-brand-navy">
            <Award className="h-6 w-6" />
          </div>
          <p className="text-sm font-medium text-neutral-900">{isOrgAdmin ? (search ? 'No certificates found' : 'No certificates yet') : 'No certificate yet'}</p>
          {!isOrgAdmin && <p className="max-w-sm text-sm text-neutral-500">
            Complete every course in your assigned Learning Path (including their quizzes) and pass your assigned
            Level Assessment, and your certificate will appear here automatically.
          </p>}
        </Card>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {certificates.map((certificate) => (
            <CertificateCard key={certificate.id} certificate={certificate} isOrgAdmin={isOrgAdmin} />
          ))}
        </div>
      )}
      {isOrgAdmin && totalCount > ADMIN_PAGE_SIZE && (
        <div className="mt-5 flex items-center justify-center gap-3">
          <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button>
          <span className="text-sm text-neutral-600">Page {page} of {Math.ceil(totalCount / ADMIN_PAGE_SIZE)}</span>
          <Button size="sm" variant="secondary" disabled={page >= Math.ceil(totalCount / ADMIN_PAGE_SIZE)} onClick={() => setPage((value) => value + 1)}>Next</Button>
        </div>
      )}
    </div>
  )
}
