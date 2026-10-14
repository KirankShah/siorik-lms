import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import { ResourceViewerPage } from './ResourceViewerPage'
import { ApiError } from '../lib/apiClient'

const mocks = vi.hoisted(() => ({
  fetchResource: vi.fn(),
  fetchResourcePdfBlob: vi.fn(),
}))

vi.mock('react-router-dom', () => ({ useParams: () => ({ id: '2' }) }))
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { first_name: 'Learner', last_name: 'One', email: 'learner@example.com' } }),
}))
vi.mock('../components/player/ContentProtectionBoundary', () => ({
  ContentProtectionBoundary: ({ children }: { children: ReactNode }) => children,
}))
vi.mock('../lib/resourcesApi', () => ({
  fetchResource: mocks.fetchResource,
  fetchResourcePdfBlob: mocks.fetchResourcePdfBlob,
}))
vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: vi.fn(),
}))
vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({ default: '/pdf.worker.min.mjs' }))

describe('ResourceViewerPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchResource.mockResolvedValue({
      id: 2,
      title: '1_Mandatory KYC (Walk-in FCY), over 100,000',
      description: '',
      uploaded_at: '2026-10-14T00:00:00Z',
      uploaded_by: 1,
      uploaded_by_name: 'Org Admin',
      can_delete: false,
    })
    mocks.fetchResourcePdfBlob.mockRejectedValue(new ApiError(404, { detail: 'Resource file is missing.' }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reports a missing stored PDF clearly instead of hiding it behind a generic load error', async () => {
    render(<ResourceViewerPage />)

    expect(await screen.findByText('The PDF file for this resource is missing from the server.')).toBeInTheDocument()
    expect(screen.queryByText('Could not load this document.')).not.toBeInTheDocument()
  })

  it('distinguishes access errors from missing files', async () => {
    mocks.fetchResourcePdfBlob.mockRejectedValue(new ApiError(403, { detail: 'Forbidden.' }))
    render(<ResourceViewerPage />)

    expect(
      await screen.findByText('You do not have permission to view this resource, or it is no longer available.'),
    ).toBeInTheDocument()
  })

  it('shows a server error message for API failures', async () => {
    mocks.fetchResourcePdfBlob.mockRejectedValue(new ApiError(500, { detail: 'Internal server error.' }))
    render(<ResourceViewerPage />)

    expect(await screen.findByText('The server could not load this document. Please try again later.')).toBeInTheDocument()
  })
})
