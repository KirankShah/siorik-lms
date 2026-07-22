import { useState } from 'react'
import type { ReactNode } from 'react'
import { createChoice, deleteChoice, updateChoice } from '../../lib/quizApi'
import type { Choice, QuestionType } from '../../types/quiz'

interface AnswerOptionsEditorProps {
  questionId: number
  questionType: QuestionType
  choices: Choice[]
  onChanged: () => void
}

export function AnswerOptionsEditor({ questionId, questionType, choices, onChanged }: AnswerOptionsEditorProps) {
  const [error, setError] = useState<string | null>(null)

  async function withErrorHandling(action: () => Promise<unknown>, message: string) {
    try {
      await action()
      onChanged()
    } catch {
      setError(message)
    }
  }

  if (questionType === 'SHORT_ANSWER' || questionType === 'ESSAY') {
    return <p className="text-xs text-slate-400 italic">Manually graded — no answer key needed. See the Grading page once learners submit.</p>
  }

  if (questionType === 'TRUE_FALSE') {
    return (
      <TrueFalseEditor
        questionId={questionId}
        choices={choices}
        onError={setError}
        errorNode={error && <p className="text-xs text-red-600">{error}</p>}
        onChanged={onChanged}
      />
    )
  }

  if (questionType === 'SINGLE_CHOICE' || questionType === 'MULTIPLE_CHOICE' || questionType === 'MULTIPLE_ANSWER') {
    return (
      <ChoiceListEditor
        questionId={questionId}
        choices={choices}
        exclusive={questionType === 'SINGLE_CHOICE' || questionType === 'MULTIPLE_CHOICE'}
        withErrorHandling={withErrorHandling}
        error={error}
      />
    )
  }

  if (questionType === 'FILL_BLANK') {
    return <FillBlankEditor questionId={questionId} choices={choices} withErrorHandling={withErrorHandling} error={error} />
  }

  if (questionType === 'MATCHING') {
    return <MatchingEditor questionId={questionId} choices={choices} withErrorHandling={withErrorHandling} error={error} />
  }

  // ORDERING
  return <OrderingEditor questionId={questionId} choices={choices} withErrorHandling={withErrorHandling} error={error} />
}

type ErrorHandler = (action: () => Promise<unknown>, message: string) => Promise<void>

function AddRowButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick} className="mt-2 text-xs font-medium text-slate-600 hover:underline">
      {label}
    </button>
  )
}

function RemoveButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="text-slate-300 hover:text-red-500" aria-label="Remove">
      ✕
    </button>
  )
}

// SINGLE_CHOICE/MULTIPLE_CHOICE (radio-style, one correct answer) and
// MULTIPLE_ANSWER (checkbox-style, several correct answers).
function ChoiceListEditor({
  questionId,
  choices,
  exclusive,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  exclusive: boolean
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  async function handleAdd() {
    await withErrorHandling(
      () => createChoice({ question: questionId, choice_text: 'New option', is_correct: false, order: choices.length + 1 }),
      'Could not add option.',
    )
  }

  async function handleToggleCorrect(choice: Choice) {
    await withErrorHandling(async () => {
      if (exclusive) {
        await Promise.all(choices.filter((c) => c.id !== choice.id && c.is_correct).map((c) => updateChoice(c.id, { is_correct: false })))
      }
      await updateChoice(choice.id, { is_correct: !choice.is_correct })
    }, 'Could not update option.')
  }

  async function handleTextChange(choice: Choice, text: string) {
    await withErrorHandling(() => updateChoice(choice.id, { choice_text: text }), 'Could not update option.')
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove option.')
  }

  return (
    <div>
      <ul className="space-y-1">
        {choices.map((choice) => (
          <li key={choice.id} className="flex items-center gap-2">
            <input
              type={exclusive ? 'radio' : 'checkbox'}
              name={`correct-${questionId}`}
              checked={choice.is_correct ?? false}
              onChange={() => void handleToggleCorrect(choice)}
            />
            <input
              defaultValue={choice.choice_text}
              onBlur={(e) => e.target.value !== choice.choice_text && void handleTextChange(choice, e.target.value)}
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <RemoveButton onClick={() => void handleRemove(choice.id)} />
          </li>
        ))}
      </ul>
      <AddRowButton onClick={() => void handleAdd()} label="+ Add option" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function TrueFalseEditor({
  questionId,
  choices,
  onChanged,
  onError,
  errorNode,
}: {
  questionId: number
  choices: Choice[]
  onChanged: () => void
  onError: (message: string | null) => void
  errorNode: ReactNode
}) {
  async function ensureSeeded() {
    if (choices.length > 0) return choices
    const created = await Promise.all([
      createChoice({ question: questionId, choice_text: 'True', is_correct: true, order: 1 }),
      createChoice({ question: questionId, choice_text: 'False', is_correct: false, order: 2 }),
    ])
    onChanged()
    return created
  }

  async function handleSelect(label: 'True' | 'False') {
    try {
      const current = await ensureSeeded()
      const target = choices.length > 0 ? choices : (current as unknown as Choice[])
      await Promise.all(target.map((c) => updateChoice(c.id, { is_correct: c.choice_text === label })))
      onChanged()
    } catch {
      onError('Could not update answer.')
    }
  }

  const trueChoice = choices.find((c) => c.choice_text === 'True')
  const falseChoice = choices.find((c) => c.choice_text === 'False')

  return (
    <div>
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name={`tf-${questionId}`}
            checked={trueChoice?.is_correct ?? false}
            onChange={() => void handleSelect('True')}
          />
          True
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name={`tf-${questionId}`}
            checked={falseChoice?.is_correct ?? false}
            onChange={() => void handleSelect('False')}
          />
          False
        </label>
      </div>
      {errorNode}
    </div>
  )
}

function FillBlankEditor({
  questionId,
  choices,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  async function handleAdd() {
    await withErrorHandling(
      () => createChoice({ question: questionId, choice_text: '', is_correct: true, order: choices.length + 1 }),
      'Could not add accepted answer.',
    )
  }

  async function handleTextChange(choice: Choice, text: string) {
    await withErrorHandling(() => updateChoice(choice.id, { choice_text: text }), 'Could not update accepted answer.')
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove accepted answer.')
  }

  return (
    <div>
      <p className="mb-1 text-xs text-slate-400">Accepted answers (the learner's typed answer is matched against any of these, case-insensitively):</p>
      <ul className="space-y-1">
        {choices.map((choice) => (
          <li key={choice.id} className="flex items-center gap-2">
            <input
              defaultValue={choice.choice_text}
              onBlur={(e) => e.target.value !== choice.choice_text && void handleTextChange(choice, e.target.value)}
              placeholder="Accepted answer"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <RemoveButton onClick={() => void handleRemove(choice.id)} />
          </li>
        ))}
      </ul>
      <AddRowButton onClick={() => void handleAdd()} label="+ Add accepted answer" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function MatchingEditor({
  questionId,
  choices,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  async function handleAdd() {
    await withErrorHandling(
      () => createChoice({ question: questionId, choice_text: '', match_text: '', order: choices.length + 1 }),
      'Could not add pair.',
    )
  }

  async function handleChange(choice: Choice, field: 'choice_text' | 'match_text', value: string) {
    await withErrorHandling(() => updateChoice(choice.id, { [field]: value }), 'Could not update pair.')
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove pair.')
  }

  return (
    <div>
      <p className="mb-1 text-xs text-slate-400">Pairs (left matches right):</p>
      <ul className="space-y-1">
        {choices.map((choice) => (
          <li key={choice.id} className="flex items-center gap-2">
            <input
              defaultValue={choice.choice_text}
              onBlur={(e) => e.target.value !== choice.choice_text && void handleChange(choice, 'choice_text', e.target.value)}
              placeholder="Item"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <span className="text-slate-400">↔</span>
            <input
              defaultValue={choice.match_text ?? ''}
              onBlur={(e) => e.target.value !== choice.match_text && void handleChange(choice, 'match_text', e.target.value)}
              placeholder="Correct match"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <RemoveButton onClick={() => void handleRemove(choice.id)} />
          </li>
        ))}
      </ul>
      <AddRowButton onClick={() => void handleAdd()} label="+ Add pair" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

function OrderingEditor({
  questionId,
  choices,
  withErrorHandling,
  error,
}: {
  questionId: number
  choices: Choice[]
  withErrorHandling: ErrorHandler
  error: string | null
}) {
  const sorted = [...choices].sort((a, b) => a.order - b.order)

  async function handleAdd() {
    await withErrorHandling(
      () => createChoice({ question: questionId, choice_text: '', order: sorted.length + 1 }),
      'Could not add item.',
    )
  }

  async function handleTextChange(choice: Choice, text: string) {
    await withErrorHandling(() => updateChoice(choice.id, { choice_text: text }), 'Could not update item.')
  }

  async function handleMove(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= sorted.length) return
    const a = sorted[index]
    const b = sorted[target]
    await withErrorHandling(
      () => Promise.all([updateChoice(a.id, { order: b.order }), updateChoice(b.id, { order: a.order })]),
      'Could not reorder items.',
    )
  }

  async function handleRemove(choiceId: number) {
    await withErrorHandling(() => deleteChoice(choiceId), 'Could not remove item.')
  }

  return (
    <div>
      <p className="mb-1 text-xs text-slate-400">Items, listed in the correct order:</p>
      <ul className="space-y-1">
        {sorted.map((choice, index) => (
          <li key={choice.id} className="flex items-center gap-2">
            <span className="w-4 shrink-0 text-xs text-slate-400">{index + 1}.</span>
            <input
              defaultValue={choice.choice_text}
              onBlur={(e) => e.target.value !== choice.choice_text && void handleTextChange(choice, e.target.value)}
              placeholder="Item"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button type="button" onClick={() => void handleMove(index, -1)} disabled={index === 0} className="text-slate-400 disabled:opacity-30">
              ↑
            </button>
            <button
              type="button"
              onClick={() => void handleMove(index, 1)}
              disabled={index === sorted.length - 1}
              className="text-slate-400 disabled:opacity-30"
            >
              ↓
            </button>
            <RemoveButton onClick={() => void handleRemove(choice.id)} />
          </li>
        ))}
      </ul>
      <AddRowButton onClick={() => void handleAdd()} label="+ Add item" />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}
