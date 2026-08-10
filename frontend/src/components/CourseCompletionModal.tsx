import { CertificateButton } from './CertificateButton'
import { Button } from './ui/Button'
import { Modal } from './ui/Modal'

interface CourseCompletionModalProps {
  courseName: string
  courseId: number
  // Whether the learner's course-wide average quiz score meets the course's
  // certificate_pass_threshold (Phase 34) — computed by the caller from
  // Enrollment.certificate_ineligible_reason (null = eligible), reusing the
  // existing backend-verified decision rather than re-deriving the 70% math
  // here.
  isEligible: boolean
  // True while the retake reset request is in flight — disables the button
  // and swaps its label so a slow request can't be double-submitted.
  isRetaking?: boolean
  onRetake: () => void
  onMaybeLater: () => void
}

export function CourseCompletionModal({
  courseName,
  courseId,
  isEligible,
  isRetaking = false,
  onRetake,
  onMaybeLater,
}: CourseCompletionModalProps) {
  if (isEligible) {
    return (
      <Modal title="Course Complete" onClose={onMaybeLater}>
        <p className="text-sm text-neutral-700">Congratulations — you've completed {courseName}!</p>
        <div className="mt-4">
          <CertificateButton courseId={courseId} />
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="Course Complete" onClose={onMaybeLater}>
      <p className="text-sm text-neutral-700">
        You didn't quite reach the pass mark for this course. Would you like to retake it?
      </p>
      <div className="mt-4 flex gap-3">
        <Button disabled={isRetaking} onClick={onRetake}>
          {isRetaking ? 'Resetting…' : 'Retake Course'}
        </Button>
        <Button variant="outline" disabled={isRetaking} onClick={onMaybeLater}>
          Maybe Later
        </Button>
      </div>
    </Modal>
  )
}
