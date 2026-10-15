import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PeriodicExamAvailabilityProvider } from './PeriodicExamAvailabilityContext'
import { usePeriodicExamAvailability } from './usePeriodicExamAvailability'
import { fetchPeriodicExamAvailability } from '../lib/periodicExamsApi'

vi.mock('./AuthContext', () => ({ useAuth: () => ({ user: { id: 1, role: 'LEARNER' } }) }))
vi.mock('../lib/periodicExamsApi', () => ({ fetchPeriodicExamAvailability: vi.fn() }))

function Probe() {
  const { availability, isLoading } = usePeriodicExamAvailability()
  return <p>{isLoading ? 'loading' : availability?.enabled ? 'enabled' : 'disabled'}</p>
}

describe('PeriodicExamAvailabilityProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchPeriodicExamAvailability).mockReset()
  })

  it('loads availability once for the authenticated layout', async () => {
    vi.mocked(fetchPeriodicExamAvailability).mockResolvedValue({ enabled: true })
    render(<PeriodicExamAvailabilityProvider><Probe /></PeriodicExamAvailabilityProvider>)
    await waitFor(() => expect(screen.getByText('enabled')).toBeInTheDocument())
    expect(fetchPeriodicExamAvailability).toHaveBeenCalledTimes(1)
  })

  it('fails closed when availability cannot be loaded', async () => {
    vi.mocked(fetchPeriodicExamAvailability).mockImplementation(async () => {
      throw new Error('offline')
    })
    render(<PeriodicExamAvailabilityProvider><Probe /></PeriodicExamAvailabilityProvider>)
    await waitFor(() => expect(screen.getByText('disabled')).toBeInTheDocument())
    expect(fetchPeriodicExamAvailability).toHaveBeenCalledTimes(1)
  })
})
