import { useState } from 'react'
import { extractBlankIndexes } from '../../lib/fillBlankMarkup'
import { decodeHtmlEntitiesIfPresent } from '../../lib/htmlEntities'
import { deleteQuestion, updateQuestion } from '../../lib/quizApi'
import type { FillBlankMode, Question, QuestionType } from '../../types/quiz'
import { AnswerOptionsEditor } from './AnswerOptionsEditor'
import { FillBlankSentence } from '../FillBlankSentence'
import { RichTextField } from './RichTextField'

const QUESTION_TYPES: { value: QuestionType; label: string }[] = [
  { value: 'SINGLE_CHOICE', label: 'Single Choice' },
  { value: 'MULTIPLE_ANSWER', label: 'Multiple Answer' },
  { value: 'TRUE_FALSE', label: 'True/False' },
  { value: 'FILL_BLANK', label: 'Fill in the Blank' },
  { value: 'MATCHING', label: 'Matching' },
  { value: 'ORDERING', label: 'Ordering' },
  { value: 'CATEGORIZE', label: 'Categorize' },
  { value: 'HOTSPOT', label: 'Hotspot' },
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
  const [fillBlankMode, setFillBlankMode] = useState<FillBlankMode>(question.fill_blank_mode ?? 'TEXT_INPUT')
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
        fill_blank_mode: fillBlankMode,
        order,
        points,
        marks,
        video_url: videoUrl,
        explanation,
        feedback_correct: decodeHtmlEntitiesIfPresent(feedbackCorrect),
        feedback_incorrect: decodeHtmlEntitiesIfPresent(feedbackIncorrect),
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
    <div className="rounded-lg border border-neutral-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-neutral-400">
            {index + 1}. {QUESTION_TYPES.find((t) => t.value === question.question_type)?.label} · {question.marks} marks
          </p>
          {question.question_type === 'FILL_BLANK' ? (
            <p className="mt-1 text-sm text-neutral-900">
              <FillBlankSentence
                questionText={question.question_text}
                renderBlank={(index) => (
                  <span className="mx-1 rounded border border-yellow-500 bg-yellow-100 px-1.5 text-xs font-medium text-neutral-500">
                    Blank {index}
                  </span>
                )}
              />
            </p>
          ) : (
            <div className="mt-1 text-sm text-neutral-900" dangerouslySetInnerHTML={{ __html: question.question_text }} />
          )}
          {question.image && <img src={question.image} alt="" className="mt-2 max-h-32 rounded border border-neutral-200" />}
        </div>
        <div className="flex shrink-0 gap-3 text-sm">
          <button type="button" onClick={() => setIsEditing((v) => !v)} className="font-medium text-brand-navy hover:underline">
            {isEditing ? 'Close' : 'Edit'}
          </button>
          <button type="button" onClick={() => void handleDelete()} className="font-medium text-red-600 hover:underline">
            Delete
          </button>
        </div>
      </div>

      {isEditing && (
        <div className="mt-4 space-y-3 border-t border-neutral-100 pt-4">
          <div>
            <label className="block text-xs font-medium text-neutral-700">Question body</label>
            <div className="mt-1">
              <RichTextField key={question.id} initialHtml={question.question_text} onChange={setQuestionText} placeholder="Question text…" />
            </div>
            {questionType === 'FILL_BLANK' && (
              <p className="mt-1 text-xs text-neutral-400">
                Use numbered placeholders for blanks, e.g. "Money laundering has three stages: {'{{1}}'}, {'{{2}}'}, and{' '}
                {'{{3}}'}."
                {extractBlankIndexes(questionText).length > 0
                  ? ` Detected blanks: ${extractBlankIndexes(questionText).join(', ')}.`
                  : ' No blanks detected yet.'}
              </p>
            )}
          </div>

          {questionType === 'FILL_BLANK' && (
            <div>
              <label className="block text-xs font-medium text-neutral-700">Answer mode</label>
              <select
                value={fillBlankMode}
                onChange={(e) => setFillBlankMode(e.target.value as FillBlankMode)}
                className="mt-1 w-full max-w-xs rounded border border-neutral-300 px-2 py-1 text-sm"
              >
                <option value="TEXT_INPUT">Text input — the learner types each blank</option>
                <option value="WORD_BANK">Word bank — the learner drags tokens into each blank</option>
              </select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="block text-xs font-medium text-neutral-700">Type</label>
              <select
                value={questionType}
                onChange={(e) => setQuestionType(e.target.value as QuestionType)}
                className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
              >
                {QUESTION_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-700">Order</label>
              <input
                type="number"
                value={order}
                onChange={(e) => setOrder(Number(e.target.value))}
                className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-700">Points (scoring)</label>
              <input
                type="number"
                value={points}
                onChange={(e) => setPoints(Number(e.target.value))}
                className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-700">Marks (display)</label>
              <input
                type="number"
                value={marks}
                onChange={(e) => setMarks(Number(e.target.value))}
                className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-neutral-700">Image (optional)</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setImage(e.target.files?.[0] ?? null)}
                className="mt-1 w-full text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-700">Video URL (optional)</label>
              <input
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
                placeholder="https://…"
                className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
              />
            </div>
          </div>

        </div>
      )}

      <div className="mt-3 border-t border-neutral-100 pt-3">
        <p className="mb-1 text-xs font-medium text-neutral-500">Answer key</p>
        <AnswerOptionsEditor
          questionId={question.id}
          questionType={isEditing ? questionType : question.question_type}
          fillBlankMode={isEditing ? fillBlankMode : (question.fill_blank_mode ?? 'TEXT_INPUT')}
          choices={question.choices}
          buckets={question.buckets}
          categorizeItems={question.categorize_items}
          image={question.image}
          hotspotRegions={question.hotspot_regions}
          wordBankTokens={question.word_bank_tokens}
          onChanged={onChanged}
        />

        {isEditing && (
          <div className="mt-4 space-y-3 border-t border-neutral-100 pt-4">
            <div>
              <label className="block text-xs font-medium text-neutral-700">Explanation (shown to the learner after submission)</label>
              <div className="mt-1">
                <RichTextField
                  key={question.id}
                  initialHtml={question.explanation ?? ''}
                  onChange={setExplanation}
                  placeholder="Explain the correct answer…"
                  minHeight="80px"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-neutral-700">Feedback if correct</label>
                <textarea
                  value={feedbackCorrect}
                  onChange={(e) => setFeedbackCorrect(e.target.value)}
                  rows={2}
                  className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-700">Feedback if incorrect</label>
                <textarea
                  value={feedbackIncorrect}
                  onChange={(e) => setFeedbackIncorrect(e.target.value)}
                  rows={2}
                  className="mt-1 w-full rounded border border-neutral-300 px-2 py-1 text-sm"
                />
              </div>
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={isSaving}
              className="rounded-md bg-brand-navy px-3 py-1.5 text-xs font-medium text-white transition hover:bg-brand-navy-light disabled:opacity-60"
            >
              {isSaving ? 'Saving…' : 'Save question'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
