import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { deleteLevelQuestion, fetchLevelQuestionUsage } from '../../lib/levelAssessmentsApi'

interface DeleteQuestionModalProps {
  questionId: number
  onClose: () => void
  onDeleted: () => void
}

// Two-step delete regardless of usage history: this first step just shows
// what's about to happen (and the usage warning, if any) with a "Delete"
// button; a second, distinct confirm step is where the destructive call
// actually fires — see `stage` below.
export function DeleteQuestionModal({ questionId, onClose, onDeleted }: DeleteQuestionModalProps) {
  const [stage, setStage] = useState<'loading' | 'confirm' | 'final-confirm' | 'deleting' | 'error'>('loading')
  const [attemptCount, setAttemptCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchLevelQuestionUsage(questionId)
      .then((usage) => {
        setAttemptCount(usage.attempt_count)
        setStage('confirm')
      })
      .catch(() => {
        setError('Could not check this question\'s usage history.')
        setStage('error')
      })
  }, [questionId])

  async function handleFinalConfirm() {
    setStage('deleting')
    try {
      await deleteLevelQuestion(questionId)
      onDeleted()
    } catch {
      setError('Could not delete this question. Please try again.')
      setStage('error')
    }
  }

  return (
    <Modal title="Delete Question" onClose={onClose}>
      {stage === 'loading' && <p className="text-sm text-neutral-500">Checking usage history…</p>}

      {stage === 'error' && <p className="text-sm text-red-600">{error}</p>}

      {stage === 'confirm' && (
        <div className="space-y-4">
          {attemptCount !== null && attemptCount > 0 ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              This question has been used in <strong>{attemptCount}</strong> past attempt
              {attemptCount === 1 ? '' : 's'}. Deleting it is permanent — those attempts' results will show
              "This question has since been removed from the question bank" in its place, but the rest of
              each attempt's results are unaffected.
            </div>
          ) : (
            <p className="text-sm text-neutral-600">This question has never been used in a past attempt.</p>
          )}
          <p className="text-sm text-neutral-600">This action cannot be undone.</p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => setStage('final-confirm')}>
              Delete
            </Button>
          </div>
        </div>
      )}

      {stage === 'final-confirm' && (
        <div className="space-y-4">
          <p className="text-sm font-medium text-neutral-900">
            Are you absolutely sure you want to permanently delete this question?
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setStage('confirm')}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => void handleFinalConfirm()}>
              Yes, delete permanently
            </Button>
          </div>
        </div>
      )}

      {stage === 'deleting' && <p className="text-sm text-neutral-500">Deleting…</p>}
    </Modal>
  )
}
