import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CourseCompletionModal } from './CourseCompletionModal'
import * as certificatesApi from '../lib/certificatesApi'

vi.mock('../lib/certificatesApi')

// The 70% pass/fail branch is decided server-side by
// certificates.services.certificate_ineligibility_reason (see the backend
// boundary tests in CourseAverageCertificateEligibilityTests for the actual
// 70.0%-vs-69.9% arithmetic). This component only needs to render the right
// branch for the resulting boolean — isEligible=true stands in for "average
// >= 70%", isEligible=false for "average < 70%" (e.g. exactly 69.9%).
describe('CourseCompletionModal', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows the certificate path and no retake path when the average is at or above 70% (isEligible=true)', () => {
    render(
      <CourseCompletionModal
        courseName="AML Fundamentals"
        courseId={1}
        isEligible={true}
        onRetake={vi.fn()}
        onMaybeLater={vi.fn()}
      />,
    )

    expect(screen.getByText(/Congratulations.*AML Fundamentals/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Download Certificate/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retake Course' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Maybe Later' })).not.toBeInTheDocument()
  })

  it('shows the retake path and no certificate path when the average is below 70% (isEligible=false, e.g. 69.9%)', () => {
    render(
      <CourseCompletionModal
        courseName="AML Fundamentals"
        courseId={1}
        isEligible={false}
        onRetake={vi.fn()}
        onMaybeLater={vi.fn()}
      />,
    )

    expect(screen.getByText(/didn't quite reach the pass mark/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retake Course' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Maybe Later' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Download Certificate/ })).not.toBeInTheDocument()
  })

  it('calls onRetake when Retake Course is clicked', () => {
    const onRetake = vi.fn()
    render(
      <CourseCompletionModal courseName="AML Fundamentals" courseId={1} isEligible={false} onRetake={onRetake} onMaybeLater={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Retake Course' }))
    expect(onRetake).toHaveBeenCalledTimes(1)
  })

  it('disables both buttons and shows a resetting label while the retake request is in flight', () => {
    render(
      <CourseCompletionModal
        courseName="AML Fundamentals"
        courseId={1}
        isEligible={false}
        isRetaking={true}
        onRetake={vi.fn()}
        onMaybeLater={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Resetting…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Maybe Later' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Retake Course' })).not.toBeInTheDocument()
  })

  it('calls onMaybeLater when Maybe Later is clicked', () => {
    const onMaybeLater = vi.fn()
    render(
      <CourseCompletionModal
        courseName="AML Fundamentals"
        courseId={1}
        isEligible={false}
        onRetake={vi.fn()}
        onMaybeLater={onMaybeLater}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Maybe Later' }))
    expect(onMaybeLater).toHaveBeenCalledTimes(1)
  })

  it('triggers the existing certificate issue/download flow when Download Certificate is clicked', async () => {
    vi.mocked(certificatesApi.issueCertificate).mockResolvedValue({
      id: 1,
      certificate_number: 'SIORIK-2026-000001',
    } as never)
    vi.mocked(certificatesApi.downloadCertificate).mockResolvedValue(undefined)

    render(
      <CourseCompletionModal courseName="AML Fundamentals" courseId={1} isEligible={true} onRetake={vi.fn()} onMaybeLater={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Download Certificate/ }))

    await waitFor(() => expect(certificatesApi.issueCertificate).toHaveBeenCalledWith(1))
    expect(certificatesApi.downloadCertificate).toHaveBeenCalled()
  })
})
