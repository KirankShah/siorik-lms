// Shared choice-list "taking" UI for any single/multi-select question — used
// by QuizPlayer (course quizzes, Phase 4/13) and LevelAssessmentPlayer
// (standalone role-based assessments) so this rendering exists in one place
// rather than being rebuilt per consumer.
export interface ChoiceOption {
  id: number
  choice_text: string
}

interface ChoiceQuestionAnswerProps {
  questionId: number
  isMultiple: boolean
  choices: ChoiceOption[]
  selected: Set<number>
  onToggle: (choiceId: number) => void
}

export function ChoiceQuestionAnswer({ questionId, isMultiple, choices, selected, onToggle }: ChoiceQuestionAnswerProps) {
  return (
    <div className="space-y-2">
      {choices.map((choice) => {
        const isSelected = selected.has(choice.id)
        return (
          <label
            key={choice.id}
            className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition ${
              isSelected ? 'border-brand-navy bg-brand-navy/5' : 'border-neutral-200 hover:bg-neutral-50'
            }`}
          >
            <input
              type={isMultiple ? 'checkbox' : 'radio'}
              name={`question-${questionId}`}
              checked={isSelected}
              onChange={() => onToggle(choice.id)}
              className="h-4 w-4"
            />
            {choice.choice_text}
          </label>
        )
      })}
    </div>
  )
}
