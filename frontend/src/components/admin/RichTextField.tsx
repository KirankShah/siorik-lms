import { useEffect, useRef } from 'react'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'
import './richTextField.css'

interface RichTextFieldProps {
  initialHtml: string
  onChange: (html: string) => void
  placeholder?: string
  minHeight?: string
  // Fires with the hex value whenever the instructor picks a text or
  // highlight swatch. Optional — most callers (question/assignment/scenario
  // text) have no background to check contrast against.
  onColorApplied?: (kind: 'color' | 'background', hex: string) => void
}

// Text/highlight swatches limited to the Phase 19 brand tokens, two neutral
// grays, and white (Phase 27 — dark slide templates like Deep Navy Dark and
// Charcoal Dark need a legible text/highlight option) — deliberately not
// Quill's full arbitrary color picker, so instructor-authored content stays
// visually consistent across courses.
const SWATCH_COLORS = ['#032147', '#053c82', '#e1b862', '#334155', '#e2e8f0', '#ffffff']

// Display names for the per-swatch tooltip — see the ql-picker-item title
// wiring below. Keys are lowercase hex to match Quill's own data-value.
const SWATCH_NAMES: Record<string, string> = {
  '#032147': 'Navy',
  '#053c82': 'Navy Light',
  '#e1b862': 'Gold',
  '#334155': 'Slate',
  '#e2e8f0': 'Light Gray',
  '#ffffff': 'White',
}

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

// Quill's toolbar pickers (font/size/color/background/align) open a dropdown
// (`.ql-picker-options`) that's `position: absolute` relative to the picker
// by default — anchored inside whatever ancestor happens to clip overflow
// (here, the Edit-element Modal's scrollable body), so a picker near the
// modal's bottom or right edge gets its dropdown cut off, hiding options
// (including the white swatch, the last one in the row). Re-anchoring it to
// `position: fixed` with a rect computed against the real viewport escapes
// that clipping entirely and lets it flip upward / clamp sideways when
// there isn't room — a bigger modal (see ElementFormModal) makes this less
// likely to trigger, but doesn't prevent it outright near screen edges.
function repositionPickerDropdown(picker: HTMLElement) {
  const options = picker.querySelector<HTMLElement>('.ql-picker-options')
  const label = picker.querySelector<HTMLElement>('.ql-picker-label')
  if (!options || !label) return

  // quill.snow.css sizes .ql-picker-options with `min-width: 100%` — under
  // its default `position: absolute` that 100% resolves against the small
  // picker itself (correct, compact size), but min-width still applies
  // under `position: fixed` too, where the containing block becomes the
  // *viewport* instead — that's what previously blew every dropdown up to
  // near-screen width the moment this function switched it to fixed. Clear
  // any inline overrides left from a previous open first, so the natural
  // width below is measured while still governed by the stylesheet's
  // absolute/min-width:100%-of-picker sizing, not stale fixed-position
  // values from last time.
  options.style.position = ''
  options.style.width = ''
  options.style.minWidth = ''
  options.style.margin = ''
  options.style.top = ''
  options.style.bottom = ''
  options.style.left = ''

  const labelRect = label.getBoundingClientRect()
  const naturalRect = options.getBoundingClientRect()
  const naturalWidth = naturalRect.width
  const naturalHeight = naturalRect.height

  options.style.position = 'fixed'
  options.style.margin = '0'
  // Lock in the size just measured — without this, min-width:100% recomputes
  // against the viewport now that position is fixed, which is the actual
  // regression this pins down.
  options.style.width = `${naturalWidth}px`
  options.style.minWidth = '0'

  const opensUpward = labelRect.bottom + naturalHeight + 4 > window.innerHeight
  if (opensUpward) {
    options.style.top = ''
    options.style.bottom = `${window.innerHeight - labelRect.top + 4}px`
  } else {
    options.style.top = `${labelRect.bottom + 4}px`
    options.style.bottom = ''
  }

  const maxLeft = window.innerWidth - naturalWidth - 8
  options.style.left = `${Math.max(8, Math.min(labelRect.left, maxLeft))}px`
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

// Quill's own getSemanticHTML() (the method handleTextChange calls to build
// what actually gets saved) has a confirmed bug: it correctly serializes the
// `align` attribute for plain paragraphs, but silently drops it specifically
// for list-item lines, even though the live DOM and quill.getContents()'s
// Delta both have it recorded correctly right up until that HTML export step
// — reproduced directly against the installed quill package: selecting a
// <ul>/<ol> and clicking Center/Right/Justify updates the editor's own DOM
// immediately, but the align class never survives into the HTML that
// actually gets persisted. This patches it back in afterwards using the
// Delta (which is reliable) as the source of truth, since patching Quill
// itself isn't an option.
//
// A Delta line's attributes live on whichever op contains its trailing '\n'
// (Quill's Delta format), not on the line's text content, and one op's
// insert can in principle close more than one line if consecutive lines
// share identical attributes — hence counting '\n' occurrences per op below
// rather than assuming one line per op.
function listLineAlignments(delta: { ops: { insert?: unknown; attributes?: Record<string, unknown> }[] }): (string | undefined)[] {
  const aligns: (string | undefined)[] = []
  for (const op of delta.ops) {
    if (typeof op.insert !== 'string' || !op.attributes?.list) continue
    const lineBreaks = op.insert.length - op.insert.replaceAll('\n', '').length
    for (let i = 0; i < lineBreaks; i++) {
      aligns.push(op.attributes.align as string | undefined)
    }
  }
  return aligns
}

// A second, separate getSemanticHTML() gap around lists: when an indented
// list line has no preceding same-or-lower-level sibling to nest under (the
// very first item in a list is indented, or an item jumps more than one
// indent level at once), Quill wraps the resulting nested <ul>/<ol> in an
// empty synthetic <li> rather than omitting it — confirmed directly against
// the installed quill package. Reconstructing "proper" nested-list HTML from
// Quill's flat per-line indent model is inherently ambiguous in exactly this
// situation (there's no real content to hang the intermediate level off of),
// so rather than hand-roll a replacement for Quill's own imperfect
// algorithm, this just tags the resulting empty wrapper so
// richTextContent.css can hide its otherwise-stray bullet/number marker.
// The wrapper is reliably identifiable by string adjacency alone — a real,
// non-empty list line always has some text (even just &nbsp;) immediately
// after its opening <li>, so `<li><ul`/`<li><ol` with nothing between only
// ever occurs for this synthetic case. (A pure-CSS `:has(> ul:only-child)`
// selector looks tempting but is wrong: `:only-child` ignores text nodes, so
// it also matches legitimate `<li>Item<ul>...` nesting — telling the two
// apart needs the raw HTML string, not just the parsed element tree.)
function markPhantomListWrappers(html: string): string {
  return html.replace(/<li>(?=<[uo]l>)/g, '<li class="ql-empty-list-wrapper">')
}

// <li> tags in getSemanticHTML()'s output currently never carry any
// attribute of their own (confirmed against the installed quill version) —
// matching only that exact `<li>` shape is deliberate: if a future quill
// version fixes the underlying bug and starts emitting `class="ql-align-*"`
// itself, the `( class="[^"]*")?` branch below matches that too and this
// function becomes a no-op rather than double-applying the class. Must run
// after markPhantomListWrappers, and must skip (not just leave unmodified)
// any <li> that function already tagged: a phantom wrapper has no
// corresponding Delta line at all, so counting it here would shift every
// subsequent real list line's lookup into `aligns` off by one.
function patchListItemAlignment(html: string, delta: { ops: { insert?: unknown; attributes?: Record<string, unknown> }[] }): string {
  const aligns = listLineAlignments(delta)
  if (aligns.length === 0) return html
  let lineIndex = 0
  return html.replace(/<li( class="[^"]*")?>/g, (match, existingClass: string | undefined) => {
    if (existingClass?.includes('ql-empty-list-wrapper')) return match
    const align = aligns[lineIndex]
    lineIndex += 1
    return existingClass || !align ? match : `<li class="ql-align-${align}">`
  })
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
export function RichTextField({
  initialHtml,
  onChange,
  placeholder,
  minHeight = '120px',
  onColorApplied,
}: RichTextFieldProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const onColorAppliedRef = useRef(onColorApplied)
  onColorAppliedRef.current = onColorApplied

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

    // Individual swatches get no label from Quill at all (not even the hex
    // value) — name each one so instructors aren't guessing from color alone.
    toolbarEl.querySelectorAll('.ql-color .ql-picker-item, .ql-background .ql-picker-item').forEach((el) => {
      const value = (el as HTMLElement).dataset.value
      const name = value && SWATCH_NAMES[value]
      if (name) el.setAttribute('title', name)
    })

    // Quill's picker wraps a native <select>; it dispatches a 'change' event
    // on the swatch the instructor just picked (see Picker.selectItem in
    // Quill's own source), which is also what the toolbar module itself
    // listens to in order to apply the format. Piggybacking the same event
    // lets callers react to a color pick (e.g. a readability warning against
    // the slide's background) without RichTextField knowing anything about
    // slide templates itself.
    const colorSelect = toolbarEl.querySelector<HTMLSelectElement>('select.ql-color')
    const backgroundSelect = toolbarEl.querySelector<HTMLSelectElement>('select.ql-background')
    function handleColorSelectChange() {
      if (colorSelect?.value) onColorAppliedRef.current?.('color', colorSelect.value)
    }
    function handleBackgroundSelectChange() {
      if (backgroundSelect?.value) onColorAppliedRef.current?.('background', backgroundSelect.value)
    }
    colorSelect?.addEventListener('change', handleColorSelectChange)
    backgroundSelect?.addEventListener('change', handleBackgroundSelectChange)

    // Re-anchor a picker's dropdown against the viewport the moment it
    // opens (Quill toggles `ql-expanded` on the picker itself) — see
    // repositionPickerDropdown's own comment for why this is necessary
    // rather than just a CSS fix.
    const pickers = toolbarEl.querySelectorAll<HTMLElement>('.ql-picker')
    let openPicker: HTMLElement | null = null
    const pickerObserver = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        const picker = mutation.target as HTMLElement
        if (picker.classList.contains('ql-expanded')) {
          openPicker = picker
          repositionPickerDropdown(picker)
        } else if (openPicker === picker) {
          openPicker = null
        }
      }
    })
    pickers.forEach((picker) => pickerObserver.observe(picker, { attributes: true, attributeFilter: ['class'] }))
    function handleViewportChange() {
      if (openPicker) repositionPickerDropdown(openPicker)
    }
    window.addEventListener('resize', handleViewportChange)

    function handleTextChange(_delta: unknown, _oldDelta: unknown, source: string) {
      if (source !== Quill.sources.USER) return
      const html = markPhantomListWrappers(quill.getSemanticHTML())
      onChangeRef.current(patchListItemAlignment(html, quill.getContents()))
    }

    quill.on('text-change', handleTextChange)

    return () => {
      quill.off('text-change', handleTextChange)
      pickerObserver.disconnect()
      window.removeEventListener('resize', handleViewportChange)
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
