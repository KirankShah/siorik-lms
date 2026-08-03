import { FillBlankSentence } from './FillBlankSentence'

interface FillBlankTextAnswerProps {
  questionText: string
  values: Record<number, string>
  onChange: (blankIndex: number, value: string) => void
}

// Renders the question text with a fully-controlled <input> inline at each
// {{N}} placeholder — a first-class part of the React tree, not something
// injected into raw HTML after the fact (no dangerouslySetInnerHTML, no
// querySelector, no portals).
export function FillBlankTextAnswer({ questionText, values, onChange }: FillBlankTextAnswerProps) {
  return (
    <div className="text-sm leading-relaxed text-neutral-900">
      <FillBlankSentence
        questionText={questionText}
        renderBlank={(index) => (
          <input
            type="text"
            maxLength={12}
            value={values[index] ?? ''}
            onChange={(e) => onChange(index, e.target.value)}
            placeholder="Your answer..."
            className="mx-1 inline-block w-[12ch] rounded border border-yellow-500 bg-yellow-200 px-2 py-0.5 text-sm align-middle text-neutral-900 focus:outline-none focus:ring-2 focus:ring-yellow-500"
          />
        )}
      />
    </div>
  )
}
