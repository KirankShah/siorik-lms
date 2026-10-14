import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { CertificatesPage } from './CertificatesPage'

const mocks = vi.hoisted(() => ({
  user: { role: 'ORG_ADMIN' as string },
  fetchCertificates: vi.fn(),
  fetchAdminCertificates: vi.fn(),
  downloadAdminCertificatesZip: vi.fn(),
  downloadBlob: vi.fn(),
  downloadCertificate: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: mocks.user }) }))
vi.mock('../lib/certificatesApi', () => ({
  fetchCertificates: mocks.fetchCertificates,
  fetchAdminCertificates: mocks.fetchAdminCertificates,
  downloadAdminCertificatesZip: mocks.downloadAdminCertificatesZip,
  downloadBlob: mocks.downloadBlob,
  downloadCertificate: mocks.downloadCertificate,
}))

const adminCertificate = {
  id: 1,
  staff_name: 'Asha Gurung',
  staff_email: 'asha@example.com',
  level: 'Officer Level',
  title: 'Learning Path Certificate',
  issued_at: '2026-10-07T00:00:00Z',
  certificate_number: 'SIORIK-2026-000001',
}

describe('CertificatesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.user.role = 'ORG_ADMIN'
    mocks.fetchAdminCertificates.mockResolvedValue({ count: 1, next: null, previous: null, results: [adminCertificate] })
    mocks.fetchCertificates.mockResolvedValue([])
  })

  it('shows staff name, email, level, and the search box for org admins', async () => {
    render(<CertificatesPage />)
    expect(await screen.findByText('Asha Gurung')).toBeInTheDocument()
    expect(screen.getByText('asha@example.com')).toBeInTheDocument()
    expect(screen.getByText('Officer Level')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Search staff name or email' })).toBeInTheDocument()
  })

  it('shows the filtered result count on Download all and searches through the API', async () => {
    render(<CertificatesPage />)
    expect(await screen.findByRole('button', { name: 'Download all (1)' })).toBeInTheDocument()
    fireEvent.change(screen.getByRole('textbox', { name: 'Search staff name or email' }), { target: { value: 'asha' } })
    await waitFor(() => expect(mocks.fetchAdminCertificates).toHaveBeenLastCalledWith({ search: 'asha', sort: 'newest', page: 1 }))
  })

  it('shows the no-result state and disables Download all for an empty result', async () => {
    mocks.fetchAdminCertificates.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    render(<CertificatesPage />)
    fireEvent.change(await screen.findByRole('textbox', { name: 'Search staff name or email' }), { target: { value: 'missing' } })
    expect(await screen.findByText('No certificates found')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download all (0)' })).toBeDisabled()
  })

  it('keeps the learner page private from admin search and download-all controls', async () => {
    mocks.user.role = 'LEARNER'
    render(<CertificatesPage />)
    await waitFor(() => expect(mocks.fetchCertificates).toHaveBeenCalled())
    expect(screen.queryByRole('textbox', { name: 'Search staff name or email' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Download all/ })).not.toBeInTheDocument()
    expect(mocks.fetchAdminCertificates).not.toHaveBeenCalled()
  })
})
