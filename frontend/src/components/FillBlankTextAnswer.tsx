import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { injectBlankMarkup } from '../lib/fillBlankMarkup'

interface FillBlankTextAnswerProps {
  questionHtml: string
  values: Record<number, string>
  onChange: (blankIndex: number, value: string) => void
}

// Portals a text input into each {{N}} placeholder's <span> marker (see
// injectBlankMarkup), so the blank sits inline within the question's own
// HTML instead of in a separate list below it.
export function FillBlankTextAnswer({ questionHtml, values, onChange }: FillBlankTextAnswerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [targets, setTargets] = useState<Record<number, HTMLElement>>({})
  const injectedHtml = useMemo(() => injectBlankMarkup(questionHtml), [questionHtml])

  useLayoutEffect(() => {
    if (!containerRef.current) return
    const found: Record<number, HTMLElement> = {}
    containerRef.current.querySelectorAll('[data-blank-index]').forEach((el) => {
      found[Number(el.getAttribute('data-blank-index'))] = el as HTMLElement
    })
    setTargets(found)
  }, [injectedHtml])

  return (
    <div>
      <div ref={containerRef} className="text-sm leading-relaxed text-neutral-900" dangerouslySetInnerHTML={{ __html: injectedHtml }} />
      {Object.entries(targets).map(([indexStr, el]) => {
        const index = Number(indexStr)
        return createPortal(
          <input
            type="text"
            value={values[index] ?? ''}
            onChange={(e) => onChange(index, e.target.value)}
            placeholder={`Blank ${index}`}
            className="mx-1 inline-block w-32 rounded border border-neutral-300 px-2 py-0.5 text-sm align-middle"
          />,
          el,
          `blank-${index}`,
        )
      })}
    </div>
  )
}
