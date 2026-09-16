import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Modal } from '../ui/Modal'
import { ApiError } from '../../lib/apiClient'
import { fetchLevelQuestion, updateLevelQuestion } from '../../lib/levelAssessmentsApi'
import type { LevelQuestionEditInput, LevelQuestionOptions, LevelQuestionType } from '../../types/levelAssessments'

const OPTION_LETTERS: (keyof LevelQuestionOptions)[] = ['A', 'B', 'C', 'D', 'E']
const EMPTY_OPTIONS: LevelQuestionOptions = { A: '', B: '', C: '', D: '', E: '' }

const textareaClass = 'mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm shadow-sm focus:border-brand-navy focus:ring-1 focus:ring-brand-navy focus:outline-none'

interface QuestionEditModalProps {
  questionId: number
  onClose: () => void
  onSaved: () => void
}

export function QuestionEditModal({ questionId, onClose, onSaved }: QuestionEditModalProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [questionText, setQuestionText] = useState('')
  const [questionType, setQuestionType] = useState<LevelQuestionType>('SINGLE_CHOICE')
  const [options, setOptions] = useState<LevelQuestionOptions>(EMPTY_OPTIONS)
  const [correctAnswers, setCorrectAnswers] = useState<string[]>([])
  const [marks, setMarks] = useState(1)
  const [explanation, setExplanation] = useState('')
  const [feedbackCorrect, setFeedbackCorrect] = useState('')
  const [feedbackIncorrect, setFeedbackIncorrect] = useState('')

  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    setIsLoading(true)
    fetchLevelQuestion(questionId)
      .then((detail) => {
        setQuestionText(detail.question_text)
        setQuestionType(detail.question_type)
        setOptions(detail.options)
        setCorrectAnswers(detail.correct_answers)
        setMarks(detail.marks)
        setExplanation(detail.explanation)
        setFeedbackCorrect(detail.feedback_correct)
        setFeedbackIncorrect(detail.feedback_incorrect)
      })
      .catch(() => setLoadError('Could not load this question.'))
      .finally(() => setIsLoading(false))
  }, [questionId])

  function toggleCorrectAnswer(letter: string) {
    if (questionType === 'SINGLE_CHOICE') {
      setCorrectAnswers([letter])
      return
    }
    setCorrectAnswers((current) =>
      current.includes(letter) ? current.filter((l) => l !== letter) : [...current, letter],
    )
  }

  function handleQuestionTypeChange(value: LevelQuestionType) {
    setQuestionType(value)
    // Switching to Single Choice with more than one already checked would
    // otherwise submit an invalid combination — same rule the Excel import
    // enforces (imports.parse_correct_answers).
    if (value === 'SINGLE_CHOICE' && correctAnswers.length > 1) {
      setCorrectAnswers(correctAnswers.slice(0, 1))
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaveError(null)
    setIsSaving(true)
    try {
      const input: LevelQuestionEditInput = {
        question_text: questionText,
        question_type: questionType,
        options,
        correct_answers: correctAnswers,
        marks,
        explanation,
        feedback_correct: feedbackCorrect,
        feedback_incorrect: feedbackIncorrect,
      }
      await updateLevelQuestion(questionId, input)
      onSaved()
    } catch (err) {
      if (err instanceof ApiError && err.body && typeof err.body === 'object') {
        const body = err.body as Record<string, string[] | undefined>
        const message =
          body.correct_answers?.[0] ?? body.marks?.[0] ?? body.question_text?.[0] ?? body.options?.[0]
        setSaveError(message ?? 'Could not save this question.')
      } else {
        setSaveError('Could not save this question.')
      }
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Modal
      title="View / Edit Question"
      onClose={onClose}
      widthClassName="max-w-2xl"
      footer={
        !isLoading &&
        !loadError && (
          <>
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="question-edit-form" disabled={isSaving}>
              {isSaving ? 'Saving…' : 'Save changes'}
            </Button>
          </>
        )
      }
    >
      {isLoading ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : loadError ? (
        <p className="text-sm text-red-600">{loadError}</p>
      ) : (
        <form id="question-edit-form" onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700">Question Text</label>
            <textarea
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              required
              rows={3}
              className={textareaClass}
            />
          </div>

          <div className="flex gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700">Question Type</label>
              <select
                value={questionType}
                onChange={(e) => handleQuestionTypeChange(e.target.value as LevelQuestionType)}
                className="mt-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
              >
                <option value="SINGLE_CHOICE">Single choice</option>
                <option value="MULTIPLE_ANSWER">Multiple answer</option>
              </select>
            </div>
            <Input
              id="marks"
              label="Marks"
              type="number"
              min={1}
              value={marks}
              onChange={(e) => setMarks(Number(e.target.value))}
              className="w-24"
              required
            />
          </div>

          <div>
            <p className="text-sm font-medium text-neutral-700">Options — check the correct answer(s)</p>
            <div className="mt-2 space-y-2">
              {OPTION_LETTERS.map((letter) => (
                <div key={letter} className="flex items-center gap-2">
                  <input
                    type={questionType === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'}
                    name="correct-answer"
                    checked={correctAnswers.includes(letter)}
                    onChange={() => toggleCorrectAnswer(letter)}
                    className="h-4 w-4 accent-brand-navy"
                  />
                  <span className="w-5 text-sm font-medium text-neutral-500">{letter}</span>
                  <input
                    type="text"
                    value={options[letter]}
                    onChange={(e) => setOptions((current) => ({ ...current, [letter]: e.target.value }))}
                    placeholder={letter === 'E' ? 'Optional' : ''}
                    className="flex-1 rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
                  />
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700">Explanation</label>
            <textarea
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              rows={2}
              className={textareaClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700">Feedback if Correct</label>
              <textarea
                value={feedbackCorrect}
                onChange={(e) => setFeedbackCorrect(e.target.value)}
                rows={2}
                className={textareaClass}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700">Feedback if Incorrect</label>
              <textarea
                value={feedbackIncorrect}
                onChange={(e) => setFeedbackIncorrect(e.target.value)}
                rows={2}
                className={textareaClass}
              />
            </div>
          </div>

          {saveError && <p className="text-sm text-red-600">{saveError}</p>}
        </form>
      )}
    </Modal>
  )
}
