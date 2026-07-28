import { apiFetch, apiFetchBlob } from './apiClient'
import type { Certificate } from '../types/certificates'

export function fetchCertificates(): Promise<Certificate[]> {
  return apiFetch<Certificate[]>('/certificates/')
}

export function issueCertificate(courseId: number): Promise<Certificate> {
  return apiFetch<Certificate>('/certificates/issue/', {
    method: 'POST',
    body: { course: courseId },
  })
}

export async function downloadCertificate(certificateId: number, filename: string): Promise<void> {
  const blob = await apiFetchBlob(`/certificates/${certificateId}/download/`)
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
