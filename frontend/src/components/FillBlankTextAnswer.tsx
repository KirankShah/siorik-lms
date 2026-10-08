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
            value={values[index] ?? ''}
            onChange={(e) => onChange(index, e.target.value)}
            placeholder="Your answer..."
            size={Math.min(Math.max((values[index] ?? '').length + 1, 12), 40)}
            className="mx-1 inline-block min-w-[12ch] max-w-full rounded border border-yellow-500 bg-yellow-200 px-2 py-0.5 text-sm align-middle text-neutral-900 focus:outline-none focus:ring-2 focus:ring-yellow-500"
          />
        )}
      />
    </div>
  )
}
