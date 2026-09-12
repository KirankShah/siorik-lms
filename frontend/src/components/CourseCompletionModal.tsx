import { useEffect, useState } from 'react'
import { CertificateButton } from './CertificateButton'
import { MilestoneMascot } from './MilestoneMascot'
import { Button } from './ui/Button'
import { Modal } from './ui/Modal'
import type { CompletedTierMilestone } from '../types/learningPath'

// Brief pause + fade/slide before the certificate button appears, only for
// the actual finale of a learner's whole Learning Path — see isPathFinale.
// Presentation polish on the existing certificate flow, not a new
// certificate type: CertificateButton itself is untouched.
const CERTIFICATE_REVEAL_DELAY_MS = 1100

function CertificateReveal({ onDownloaded }: { onDownloaded: () => void }) {
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setRevealed(true), CERTIFICATE_REVEAL_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div className="relative min-h-[42px]">
      <p
        className={`absolute inset-0 flex items-center text-sm text-neutral-500 transition-opacity duration-500 ${
          revealed ? 'pointer-events-none opacity-0' : 'opacity-100'
        }`}
      >
        Preparing your certificate…
      </p>
      <div
        className={`transition-all duration-500 ease-out ${revealed ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0'}`}
      >
        <CertificateButton onDownloaded={onDownloaded} />
      </div>
    </div>
  )
}

interface CourseCompletionModalProps {
  courseName: string
  // Whether the learner's course-wide average quiz score meets the course's
  // certificate_pass_threshold (Phase 34) — computed by the caller from
  // Enrollment.certificate_ineligible_reason (null = eligible), reusing the
  // existing backend-verified decision rather than re-deriving the 70% math
  // here. Governs only the retake-vs-congratulate branch below — no longer
  // implies a certificate is available (see isPathFinale for that).
  isEligible: boolean
  // True while the retake reset request is in flight — disables the button
  // and swaps its label so a slow request can't be double-submitted.
  isRetaking?: boolean
  // Tier(s) this specific completion just finished (see backend
  // courses.learning_path.check_learning_path_milestones) — when non-empty,
  // Mr. Siorik's milestone congratulation replaces the plain "Congratulations"
  // line. Almost always at most one entry.
  newlyCompletedTiers?: CompletedTierMilestone[]
  // True once this completion finished the learner's ENTIRE assigned
  // Learning Path — the only time a certificate exists to show. There's
  // exactly one certificate per learner (not one per course), so it never
  // appears for an ordinary, non-finale course completion.
  isPathFinale?: boolean
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
  // isPathFinale branch only: fired after the certificate has actually
  // downloaded — see CertificateButton. Navigates to the course list,
  // since this is the one action in this modal that represents "done".
  onCertificateDownloaded: () => void
}

export function CourseCompletionModal({
  courseName,
  isEligible,
  isRetaking = false,
  newlyCompletedTiers,
  isPathFinale = false,
  onRetake,
  onBackToCourse,
  onMaybeLater,
  onCertificateDownloaded,
}: CourseCompletionModalProps) {
  if (isEligible) {
    const tierJustCompleted = newlyCompletedTiers?.[0]

    return (
      <Modal title="Course Complete" onClose={onBackToCourse}>
        {tierJustCompleted ? (
          <MilestoneMascot
            message={`${tierJustCompleted.tier_label} complete — nice work, ${tierJustCompleted.course_count} down!`}
          />
        ) : (
          <p className="text-sm text-neutral-700">Congratulations — you've completed {courseName}!</p>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {isPathFinale && <CertificateReveal onDownloaded={onCertificateDownloaded} />}
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
