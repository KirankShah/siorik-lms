import { useRef } from 'react'

interface RichTextFieldProps {
  initialHtml: string
  onChange: (html: string) => void
  placeholder?: string
  minHeight?: string
}

// A deliberately small rich-text field (bold/italic/bullet/numbered list) for
// question bodies — not a full BlockNote instance, since a quiz page can have
// many questions and mounting one BlockNote editor per question (times the
// several rich-text-shaped fields a question could have) isn't worth it just
// for this much formatting. Uncontrolled by design: initialHtml only seeds
// the DOM on mount (remount via `key` to load different content), further
// prop changes are ignored so typing doesn't fight the contentEditable
// selection/cursor.
export function RichTextField({ initialHtml, onChange, placeholder, minHeight = '60px' }: RichTextFieldProps) {
  const ref = useRef<HTMLDivElement>(null)

  function exec(command: string) {
    ref.current?.focus()
    document.execCommand(command)
    onChange(ref.current?.innerHTML ?? '')
  }

  return (
    <div className="rounded-md border border-slate-300">
      <div className="flex gap-1 border-b border-slate-200 bg-slate-50 px-1.5 py-1">
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec('bold')}
          className="rounded px-1.5 py-0.5 text-xs font-bold text-slate-600 hover:bg-slate-200"
          title="Bold"
        >
          B
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec('italic')}
          className="rounded px-1.5 py-0.5 text-xs font-medium text-slate-600 italic hover:bg-slate-200"
          title="Italic"
        >
          I
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec('insertUnorderedList')}
          className="rounded px-1.5 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-200"
          title="Bullet list"
        >
          • List
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => exec('insertOrderedList')}
          className="rounded px-1.5 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-200"
          title="Numbered list"
        >
          1. List
        </button>
      </div>
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        onInput={() => onChange(ref.current?.innerHTML ?? '')}
        data-placeholder={placeholder}
        style={{ minHeight }}
        className="rich-text-field px-2 py-1.5 text-sm text-slate-900 focus:outline-none empty:before:text-slate-400 empty:before:content-[attr(data-placeholder)] [&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:list-disc [&_ul]:pl-5"
        dangerouslySetInnerHTML={{ __html: initialHtml }}
      />
    </div>
  )
}
