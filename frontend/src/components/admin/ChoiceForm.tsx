import { useState } from 'react'
import { createChoice, updateChoice } from '../../lib/quizApi'
import type { Choice } from '../../types/quiz'

interface ChoiceFormProps {
  questionId: number
  choice?: Choice
  onSaved: () => void
  onCancel: () => void
}

export function ChoiceForm({ questionId, choice, onSaved, onCancel }: ChoiceFormProps) {
  const [choiceText, setChoiceText] = useState(choice?.choice_text ?? '')
  const [isCorrect, setIsCorrect] = useState(choice?.is_correct ?? false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    if (!choiceText.trim()) return
    try {
      if (choice) {
        await updateChoice(choice.id, { choice_text: choiceText, is_correct: isCorrect })
      } else {
        await createChoice({ question: questionId, choice_text: choiceText, is_correct: isCorrect })
      }
      onSaved()
    } catch {
      setError('Could not save choice.')
    }
  }

  return (
    <div className="flex items-center gap-2">
      <input
        value={choiceText}
        onChange={(e) => setChoiceText(e.target.value)}
        placeholder="Choice text"
        className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
      />
      <label className="flex items-center gap-1 text-xs text-slate-600">
        <input type="checkbox" checked={isCorrect} onChange={(e) => setIsCorrect(e.target.checked)} />
        Correct
      </label>
      <button type="button" onClick={handleSave} className="text-sm font-medium text-emerald-700">
        Save
      </button>
      <button type="button" onClick={onCancel} className="text-sm text-slate-500">
        Cancel
      </button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
