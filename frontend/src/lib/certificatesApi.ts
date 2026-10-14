import { apiFetch, apiFetchBlob } from './apiClient'
import type { Certificate, CertificateTemplate, CertificateTemplateInput, PaginatedAdminCertificates } from '../types/certificates'

export function fetchCertificates(): Promise<Certificate[]> {
  return apiFetch<Certificate[]>('/certificates/')
}

export function fetchAdminCertificates(options: { search: string; sort: 'newest' | 'name'; page: number }): Promise<PaginatedAdminCertificates> {
  const params = new URLSearchParams({ sort: options.sort, page: String(options.page) })
  if (options.search) params.set('search', options.search)
  return apiFetch<PaginatedAdminCertificates>(`/certificates/admin-list/?${params.toString()}`)
}

export function downloadAdminCertificatesZip(search: string, sort: 'newest' | 'name', part: number): Promise<Blob> {
  const params = new URLSearchParams({ sort, part: String(part) })
  if (search) params.set('search', search)
  return apiFetchBlob(`/certificates/admin-download-all/?${params.toString()}`)
}

// Exactly one certificate per learner — earned by completing their entire
// Learning Path (every course, including its quizzes) and passing their
// assigned Level Assessment. Takes no course argument: there's no longer a
// per-course certificate to ask for. See backend
// certificates.services.generate_learning_path_certificate.
export function issueCertificate(): Promise<Certificate> {
  return apiFetch<Certificate>('/certificates/issue/', { method: 'POST' })
}

export async function downloadCertificate(certificateId: number, filename: string): Promise<void> {
  const blob = await apiFetchBlob(`/certificates/${certificateId}/download/`)
  downloadBlob(blob, filename)
}

export function downloadBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}

const FILE_FIELDS = ['background_image', 'staff_name_font_file', 'course_name_font_file', 'issue_date_font_file']

function hasFileField(input: CertificateTemplateInput): boolean {
  return FILE_FIELDS.some((key) => input[key as keyof CertificateTemplateInput] instanceof File)
}

function buildCertificateTemplateFormData(input: CertificateTemplateInput): FormData {
  const formData = new FormData()
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined || value === null) continue
    formData.append(key, value instanceof File ? value : String(value))
  }
  return formData
}

export function fetchCertificateTemplates(): Promise<CertificateTemplate[]> {
  return apiFetch<CertificateTemplate[]>('/certificate-templates/')
}

export function fetchCertificateTemplate(id: number): Promise<CertificateTemplate> {
  return apiFetch<CertificateTemplate>(`/certificate-templates/${id}/`)
}

export function createCertificateTemplate(input: CertificateTemplateInput): Promise<CertificateTemplate> {
  const body = hasFileField(input) ? buildCertificateTemplateFormData(input) : input
  return apiFetch<CertificateTemplate>('/certificate-templates/', { method: 'POST', body })
}

export function updateCertificateTemplate(id: number, input: CertificateTemplateInput): Promise<CertificateTemplate> {
  const body = hasFileField(input) ? buildCertificateTemplateFormData(input) : input
  return apiFetch<CertificateTemplate>(`/certificate-templates/${id}/`, { method: 'PATCH', body })
}
