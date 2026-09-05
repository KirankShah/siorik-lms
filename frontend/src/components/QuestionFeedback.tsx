// Shared per-question explanation/feedback block for a results screen — used
// by QuizPlayer (course quizzes) and LevelAssessmentPlayer (standalone
// role-based assessments), so this rendering exists in one place.
interface QuestionFeedbackProps {
  explanation?: string
  isCorrect?: boolean
  feedbackCorrect?: string
  feedbackIncorrect?: string
}

export function QuestionFeedback({ explanation, isCorrect, feedbackCorrect, feedbackIncorrect }: QuestionFeedbackProps) {
  return (
    <>
      {explanation && (
        <div
          className="mt-3 w-full min-w-0 rounded-md bg-neutral-50 p-3 text-sm text-neutral-700 [overflow-wrap:anywhere]"
          dangerouslySetInnerHTML={{ __html: explanation }}
        />
      )}
      {isCorrect && feedbackCorrect && <p className="mt-2 break-words text-sm text-emerald-700">{feedbackCorrect}</p>}
      {isCorrect === false && feedbackIncorrect && (
        <p className="mt-2 break-words text-sm text-red-700">{feedbackIncorrect}</p>
      )}
    </>
  )
}
