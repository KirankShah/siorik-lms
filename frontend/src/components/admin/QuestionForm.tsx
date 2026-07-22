import { useState } from 'react'
import { deleteQuestion, updateQuestion } from '../../lib/quizApi'
import type { Question, QuestionType } from '../../types/quiz'
import { AnswerOptionsEditor } from './AnswerOptionsEditor'
import { RichTextField } from './RichTextField'

const QUESTION_TYPES: { value: QuestionType; label: string }[] = [
  { value: 'SINGLE_CHOICE', label: 'Single Choice' },
  { value: 'MULTIPLE_ANSWER', label: 'Multiple Answer' },
  { value: 'TRUE_FALSE', label: 'True/False' },
  { value: 'FILL_BLANK', label: 'Fill in the Blank' },
  { value: 'MATCHING', label: 'Matching' },
  { value: 'ORDERING', label: 'Ordering' },
  { value: 'SHORT_ANSWER', label: 'Short Answer' },
  { value: 'ESSAY', label: 'Essay' },
]

interface QuestionFormProps {
  question: Question
  index: number
  onChanged: () => void
}

export function QuestionForm({ question, index, onChanged }: QuestionFormProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [questionText, setQuestionText] = useState(question.question_text)
  const [questionType, setQuestionType] = useState(question.question_type)
  const [order, setOrder] = useState(question.order)
  const [points, setPoints] = useState(question.points)
  const [marks, setMarks] = useState(question.marks)
  const [videoUrl, setVideoUrl] = useState(question.video_url ?? '')
  const [explanation, setExplanation] = useState(question.explanation ?? '')
  const [feedbackCorrect, setFeedbackCorrect] = useState(question.feedback_correct ?? '')
  const [feedbackIncorrect, setFeedbackIncorrect] = useState(question.feedback_incorrect ?? '')
  const [image, setImage] = useState<File | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    try {
      await updateQuestion(question.id, {
        question_text: questionText,
        question_type: questionType,
        order,
        points,
        marks,
        video_url: videoUrl,
        explanation,
        feedback_correct: feedbackCorrect,
        feedback_incorrect: feedbackIncorrect,
        // Only include image when a new file was actually picked — sending
        // `image: null` would clear any existing image on every save.
        ...(image ? { image } : {}),
      })
      setIsEditing(false)
      onChanged()
    } catch {
      setError('Could not save question.')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm('Delete this question and all its answer options?')) return
    try {
      await deleteQuestion(question.id)
      onChanged()
    } catch {
      setError('Could not delete question.')
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-slate-400">
            {index + 1}. {QUESTION_TYPES.find((t) => t.value === question.question_type)?.label} · {question.marks} marks
          </p>
          <div className="mt-1 text-sm text-slate-900" dangerouslySetInnerHTML={{ __html: question.question_text }} />
          {question.image && <img src={question.image} alt="" className="mt-2 max-h-32 rounded border border-slate-200" />}
        </div>
        <div className="flex shrink-0 gap-3 text-sm">
          <button type="button" onClick={() => setIsEditing((v) => !v)} className="text-slate-600 hover:underline">
            {isEditing ? 'Close' : 'Edit'}
          </button>
          <button type="button" onClick={() => void handleDelete()} className="text-red-600 hover:underline">
            Delete
          </button>
        </div>
      </div>

      {isEditing && (
        <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
          <div>
            <label className="block text-xs font-medium text-slate-700">Question body</label>
            <div className="mt-1">
              <RichTextField key={question.id} initialHtml={question.question_text} onChange={setQuestionText} placeholder="Question text…" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="block text-xs font-medium text-slate-700">Type</label>
              <select
                value={questionType}
                onChange={(e) => setQuestionType(e.target.value as QuestionType)}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              >
                {QUESTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700">Order</label>
              <input
                type="number"
                value={order}
                onChange={(e) => setOrder(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700">Points (scoring)</label>
              <input
                type="number"
                value={points}
                onChange={(e) => setPoints(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700">Marks (display)</label>
              <input
                type="number"
                value={marks}
                onChange={(e) => setMarks(Number(e.target.value))}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700">Image (optional)</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setImage(e.target.files?.[0] ?? null)}
                className="mt-1 w-full text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700">Video URL (optional)</label>
              <input
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="https://…"
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700">Explanation (shown after submission)</label>
            <textarea
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700">Feedback if correct</label>
              <textarea
                value={feedbackCorrect}
                onChange={(e) => setFeedbackCorrect(e.target.value)}
                rows={2}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700">Feedback if incorrect</label>
              <textarea
                value={feedbackIncorrect}
                onChange={(e) => setFeedbackIncorrect(e.target.value)}
                rows={2}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}

          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={isSaving}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            {isSaving ? 'Saving…' : 'Save question'}
          </button>
        </div>
      )}

      <div className="mt-3 border-t border-slate-100 pt-3">
        <p className="mb-1 text-xs font-medium text-slate-500">Answer key</p>
        <AnswerOptionsEditor questionId={question.id} questionType={question.question_type} choices={question.choices} onChanged={onChanged} />
      </div>
    </div>
  )
}
