import { useEffect, useRef } from 'react'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'
import './richTextField.css'

interface RichTextFieldProps {
  initialHtml: string
  onChange: (html: string) => void
  placeholder?: string
  minHeight?: string
}

// Text/highlight swatches limited to the Phase 19 brand tokens plus two
// neutral grays — deliberately not Quill's full arbitrary color picker, so
// instructor-authored content stays visually consistent across courses.
const SWATCH_COLORS = ['#032147', '#053c82', '#e1b862', '#334155', '#e2e8f0']

const TOOLBAR_MODULES = [
  ['bold', 'italic', 'underline', 'strike'],
  [{ font: [] }, { size: ['small', false, 'large', 'huge'] }],
  [{ color: SWATCH_COLORS }, { background: SWATCH_COLORS }],
  [{ align: [] }],
  [{ list: 'ordered' }, { list: 'bullet' }],
  [{ indent: '-1' }, { indent: '+1' }],
  ['link'],
  ['clean'],
]

// Quill's stock "color"/"background" toolbar icons are both a bare "A" glyph
// (one plain, one with a faint paint-texture behind it) — easy to mistake for
// duplicates at toolbar size. Swap in two unambiguous lucide-style glyphs
// (matching the icon set used everywhere else in the admin UI) instead: a
// plain letterform for text color, a highlighter pen for background/highlight.
// Both keep Quill's `ql-color-label` swatch bar, which Quill tints to the
// current selection's color/background on selection change.
const TEXT_COLOR_ICON = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v16"/><path d="M4 7V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v2"/><path d="M9 20h6"/><rect class="ql-color-label" x="4" y="22" width="16" height="1.5" fill="#000" stroke="none"/></svg>`
const HIGHLIGHT_COLOR_ICON = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11-6 6v3h9l3-3"/><path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/><rect class="ql-color-label" x="4" y="22" width="16" height="1.5" fill="#000" stroke="none"/></svg>`

// Quill's global icon registry — mutating it swaps the icon used by every
// Quill instance on the page. Done once at module scope, not per-mount.
const quillIcons = Quill.import('ui/icons') as Record<string, string>
quillIcons.color = TEXT_COLOR_ICON
quillIcons.background = HIGHLIGHT_COLOR_ICON

// Hover tooltips for every toolbar control — Quill's toolbar module sets
// `aria-label` on plain buttons but nothing at all on pickers (font/size/
// color/background/align), and nothing visible on hover either way.
const CONTROL_LABELS: Record<string, string> = {
  bold: 'Bold',
  italic: 'Italic',
  underline: 'Underline',
  strike: 'Strikethrough',
  align: 'Text alignment',
  font: 'Font family',
  size: 'Font size',
  color: 'Text color',
  background: 'Highlight color',
  link: 'Insert link',
  clean: 'Clear formatting',
}

function labelForControl(el: Element): string | null {
  for (const cls of Array.from(el.classList)) {
    if (!cls.startsWith('ql-')) continue
    const format = cls.slice('ql-'.length)
    const value = (el as HTMLButtonElement).value
    if (format === 'list') return value === 'ordered' ? 'Numbered list' : 'Bullet list'
    if (format === 'indent') return value === '+1' ? 'Increase indent' : 'Decrease indent'
    if (CONTROL_LABELS[format]) return CONTROL_LABELS[format]
  }
  return null
}

// A lightweight Quill instance (bold/italic/underline/strike, alignment,
// lists, indent, a small font family + font size dropdown, link, a
// brand-limited color/highlight swatch, and "clear formatting") for question
// bodies, assignment instructions, and Text/Quote slide elements — not a full
// BlockNote instance, since a quiz page can have many questions and mounting
// one BlockNote editor per question (times the several rich-text-shaped
// fields a question could have) isn't worth it just for this much
// formatting. Tab/Shift+Tab indent-outdent inside lists (and otherwise stay
// inside the field rather than moving focus away) come from Quill's own
// keyboard module, not custom bindings.
//
// Uncontrolled by design: initialHtml only seeds Quill's contents on mount
// (remount via `key` to load different content), further prop changes are
// ignored so typing doesn't fight Quill's own selection state.
export function RichTextField({ initialHtml, onChange, placeholder, minHeight = '120px' }: RichTextFieldProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    // Quill mutates whatever element it's given in place (adds classes,
    // clears its innerHTML) and inserts its toolbar as a *sibling* of that
    // element, not a child — so an incomplete cleanup here previously left a
    // stray toolbar behind under React 18 StrictMode's dev-only
    // mount→cleanup→mount cycle, producing two stacked toolbar rows. Mounting
    // Quill on a disposable child of `host` and wiping `host` on cleanup
    // guarantees both the toolbar and the editor container are removed
    // together, however many times this effect re-runs.
    const editorHost = document.createElement('div')
    host.appendChild(editorHost)

    const quill = new Quill(editorHost, {
      theme: 'snow',
      placeholder,
      modules: { toolbar: TOOLBAR_MODULES },
    })

    quill.clipboard.dangerouslyPasteHTML(initialHtml, Quill.sources.SILENT)

    const toolbarEl = (quill.getModule('toolbar') as { container: HTMLElement }).container
    toolbarEl.querySelectorAll('button, .ql-picker').forEach((el) => {
      const label = labelForControl(el)
      if (label) el.setAttribute('title', label)
    })

    function handleTextChange(_delta: unknown, _oldDelta: unknown, source: string) {
      if (source !== Quill.sources.USER) return
      onChangeRef.current(quill.getSemanticHTML())
    }

    quill.on('text-change', handleTextChange)

    return () => {
      quill.off('text-change', handleTextChange)
      host.innerHTML = ''
    }
    // Deliberately mount-only — see the "uncontrolled by design" note above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="rich-text-field-quill" style={{ '--rtf-min-height': minHeight } as React.CSSProperties}>
      <div ref={hostRef} />
    </div>
  )
}
