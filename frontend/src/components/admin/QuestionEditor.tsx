import { useState } from 'react'
import { deleteChoice, deleteQuestion, updateQuestion } from '../../lib/quizApi'
import type { Question, QuestionType } from '../../types/quiz'
import { ChoiceForm } from './ChoiceForm'

const QUESTION_TYPES: QuestionType[] = ['SINGLE_CHOICE', 'MULTIPLE_CHOICE', 'TRUE_FALSE']

interface QuestionEditorProps {
  question: Question
  index: number
  onChanged: () => void
}

export function QuestionEditor({ question, index, onChanged }: QuestionEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [questionText, setQuestionText] = useState(question.question_text)
  const [questionType, setQuestionType] = useState(question.question_type)
  const [order, setOrder] = useState(question.order)
  const [points, setPoints] = useState(question.points)
  const [isAddingChoice, setIsAddingChoice] = useState(false)
  const [editingChoiceId, setEditingChoiceId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSaveQuestion() {
    try {
      await updateQuestion(question.id, { question_text: questionText, question_type: questionType, order, points })
      setIsEditing(false)
      onChanged()
    } catch {
      setError('Could not update question.')
    }
  }

  async function handleDeleteQuestion() {
    if (!window.confirm('Delete this question and all its choices?')) return
    try {
      await deleteQuestion(question.id)
      onChanged()
    } catch {
      setError('Could not delete question.')
    }
  }

  async function handleDeleteChoice(choiceId: number) {
    if (!window.confirm('Delete this choice?')) return
    try {
      await deleteChoice(choiceId)
      onChanged()
    } catch {
      setError('Could not delete choice.')
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      {isEditing ? (
        <div className="space-y-2">
          <textarea
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            rows={2}
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <div className="flex gap-2">
            <select
              value={questionType}
              onChange={(e) => setQuestionType(e.target.value as QuestionType)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            >
              {QUESTION_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            <input
              type="number"
              value={order}
              onChange={(e) => setOrder(Number(e.target.value))}
              placeholder="Order"
              className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <input
              type="number"
              value={points}
              onChange={(e) => setPoints(Number(e.target.value))}
              placeholder="Points"
              className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button type="button" onClick={handleSaveQuestion} className="text-sm font-medium text-emerald-700">
              Save
            </button>
            <button type="button" onClick={() => setIsEditing(false)} className="text-sm text-slate-500">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between">
          <p className="text-sm font-medium text-slate-900">
            {index + 1}. {question.question_text}{' '}
            <span className="font-normal text-slate-400">
              ({question.question_type}, {question.points} pt)
            </span>
          </p>
          <div className="flex shrink-0 gap-3 text-sm">
            <button type="button" onClick={() => setIsEditing(true)} className="text-slate-600 hover:underline">
              Edit
            </button>
            <button type="button" onClick={handleDeleteQuestion} className="text-red-600 hover:underline">
              Delete
            </button>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <ul className="mt-3 space-y-1 pl-4">
        {question.choices.map((choice) => (
          <li key={choice.id}>
            {editingChoiceId === choice.id ? (
              <ChoiceForm
                questionId={question.id}
                choice={choice}
                onSaved={() => {
                  setEditingChoiceId(null)
                  onChanged()
                }}
                onCancel={() => setEditingChoiceId(null)}
              />
            ) : (
              <div className="flex items-center justify-between text-sm">
                <span className={choice.is_correct ? 'font-medium text-emerald-700' : 'text-slate-600'}>
                  {choice.choice_text}
                  {choice.is_correct === true && ' ✓'}
                </span>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setEditingChoiceId(choice.id)}
                    className="text-slate-500 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteChoice(choice.id)}
                    className="text-red-500 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>

      {isAddingChoice ? (
        <div className="mt-2 pl-4">
          <ChoiceForm
            questionId={question.id}
            onSaved={() => {
              setIsAddingChoice(false)
              onChanged()
            }}
            onCancel={() => setIsAddingChoice(false)}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setIsAddingChoice(true)}
          className="mt-2 pl-4 text-sm font-medium text-slate-900 hover:underline"
        >
          + Add choice
        </button>
      )}
    </div>
  )
}
