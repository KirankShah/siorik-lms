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
  // Dismisses the modal only — the learner stays on the course (used for the
  // "Back to Course" button, and for the modal's own X/backdrop close in
  // both branches, so closing it is never a surprise exit).
  onBackToCourse: () => void
  // Ineligible branch only: an explicit decision to skip retaking for now,
  // which — unlike onBackToCourse — does navigate away (back to the course
  // list), since there's nothing left to do on this course's player right
  // now (it isn't complete, and they've declined to retake it).
  onMaybeLater: () => void
  // Eligible branch only: fired after the certificate has actually
  // downloaded — see CertificateButton. Navigates to the course list,
  // since this is the one action in this modal that represents "done".
  onCertificateDownloaded: () => void
}

export function CourseCompletionModal({
  courseName,
  courseId,
  isEligible,
  isRetaking = false,
  onRetake,
  onBackToCourse,
  onMaybeLater,
  onCertificateDownloaded,
}: CourseCompletionModalProps) {
  if (isEligible) {
    return (
      <Modal title="Course Complete" onClose={onBackToCourse}>
        <p className="text-sm text-neutral-700">Congratulations — you've completed {courseName}!</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <CertificateButton courseId={courseId} onDownloaded={onCertificateDownloaded} />
          <Button variant="outline" onClick={onBackToCourse}>
            Back to Course
          </Button>
        </div>
      </Modal>
    )
  }

  return (
    <Modal title="Course Complete" onClose={onBackToCourse}>
      <p className="text-sm text-neutral-700">
        You didn't quite reach the pass mark for this course. Would you like to retake it?
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Button disabled={isRetaking} onClick={onRetake}>
          {isRetaking ? 'Resetting…' : 'Retake Course'}
        </Button>
        <Button variant="outline" disabled={isRetaking} onClick={onBackToCourse}>
          Back to Course
        </Button>
        <Button variant="ghost" disabled={isRetaking} onClick={onMaybeLater}>
          Maybe Later
        </Button>
      </div>
    </Modal>
  )
}
