import type { ChoiceOption } from './ChoiceQuestionAnswer'

// Shared choice-list "results" UI (selected vs. correct-answer markers) —
// same reuse rationale as ChoiceQuestionAnswer. The quiz/attempt itself never
// sends is_correct to a learner before they submit; correctIds here comes
// from the answer-key data revealed only for this one already-submitted
// answer (see backend QuizAnswerSerializer / LevelAssessmentAnswerSerializer).
interface ChoiceQuestionResultProps {
  choices: ChoiceOption[]
  selectedIds: number[]
  correctIds: number[]
}

export function ChoiceQuestionResult({ choices, selectedIds, correctIds }: ChoiceQuestionResultProps) {
  return (
    <ul className="mt-2 space-y-1">
      {choices.map((choice) => {
        const wasSelected = selectedIds.includes(choice.id)
        const knownCorrect = correctIds.includes(choice.id)
        return (
          <li
            key={choice.id}
            className={`text-sm ${
              knownCorrect ? 'font-medium text-emerald-700' : wasSelected ? 'text-neutral-900' : 'text-neutral-500'
            }`}
          >
            {wasSelected ? '●' : '○'} {choice.choice_text}
            {knownCorrect && ' (correct answer)'}
          </li>
        )
      })}
    </ul>
  )
}
