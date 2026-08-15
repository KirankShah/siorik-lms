import { useEffect, useState } from 'react'
import { CheckCircle2, FileDown } from 'lucide-react'
import { resolveVideoEmbed } from '../lib/blocknote/videoProviders'
import type { ElementAlign, SlideElement } from '../types/slides'
import './richTextContent.css'

const ALIGN_ITEMS_CLASS: Record<ElementAlign, string> = {
  LEFT: 'items-start',
  CENTER: 'items-center',
  RIGHT: 'items-end',
}

// Applied to the TEXT/QUOTE wrapper divs below — see richTextContent.css for
// what this actually maps (align/font/size/indent classes RichTextField's
// toolbar can produce, none of which have any effect without it: Quill's own
// CSS for these is scoped to `.ql-editor`, which only exists in the live
// authoring editor, never here).
const QL_CONTENT_CLASS = 'ql-content'

const NON_BREAKING_SPACE = ' '

// Word's HTML export (and content pasted from it) routinely emits &nbsp; in
// place of ordinary spaces between every word. A run of non-breaking spaces
// has no wrap points at all, so a paragraph authored this way renders as one
// unbroken line that overflows its card. A non-breaking space is never an
// intentional choice in this authoring context, so it's normalized back to a
// regular, breakable space at render time — this only affects display, never
// the stored rich_text.
function normalizeNonBreakingSpaces(html: string): string {
  return html.split(NON_BREAKING_SPACE).join(' ').replace(/&nbsp;|&#160;|&#x[aA]0;/g, ' ')
}

// Quill represents an author's blank line (pressing Enter twice) as a real,
// visibly-tall empty <p><br></p> while live-editing — but Break, the blot
// backing that <br>, has length() === 0 (quill/blots/break.js), so Quill's
// length-indexed HTML export (getSemanticHTML -> editor.getHTML ->
// convertHTML in quill/core/editor.js) walks past it and never emits the
// <br>. What lands in rich_text is a bare, content-less <p></p>. A
// content-less block's own top/bottom margins collapse into one and merge
// with its siblings' (CSS §8.3.1: adjoining margins of an empty box collapse
// through it), so no matter how many blank-line paragraphs an author added,
// they contribute nothing beyond the single mb-3 already between the real
// blocks on either side — the intentional break all but disappears, and it
// does so identically everywhere this component is used (there's only one
// rendering path here, shared by every read-only view, template-styled or
// not). Stripping these husks makes mb-3 the sole, deterministic source of
// spacing between blocks — which is why every block type below (<p>, <ul>,
// <ol>) needs its own mb-3/last-child pair, not just <p>: a blank line
// authored right after a list has nothing to fall back on otherwise.
function stripEmptyParagraphs(html: string): string {
  return html.replace(/<p>(?:\s|&nbsp;|<br\s*\/?>)*<\/p>/gi, '')
}

function richTextHtml(richText: string): string {
  if (!richText) return '<span class="text-neutral-400">Empty</span>'
  return stripEmptyParagraphs(normalizeNonBreakingSpaces(richText))
}

// DIALOGUE's own interactive click-to-advance renderer — the only
// stateful case in this file, since it's the only element type with an
// interaction of its own rather than being purely a passive display block.
// Shared as-is between the admin preview and the learner-facing player, same
// as every other element type here.
function DialogueBlock({
  element,
  dominant,
  coverFill,
  onComplete,
}: {
  element: SlideElement
  dominant: boolean
  coverFill: boolean
  // Fired once the conversation reaches its final line — ContentSlidePlayer
  // uses this to gate the slide's Next button (see SlidePlayer). Also fired
  // immediately for an unconfigured Dialogue (no scene/lines set) rather
  // than leaving Next permanently blocked by an authoring mistake — there's
  // nothing for the learner to complete in that case.
  onComplete?: () => void
}) {
  const [lineIndex, setLineIndex] = useState(0)
  const scene = element.dialogue_scene_detail
  const left = element.dialogue_character_left_detail
  const right = element.dialogue_character_right_detail
  const lines = element.dialogue_lines
  const isConfigured = !!scene && lines.length > 0
  // Both hooks run unconditionally, ahead of the early return below — a
  // conditional early return between two hook calls would violate the
  // rules of hooks (this component would call a different number of hooks
  // depending on isConfigured).
  const isLastLine = isConfigured && lineIndex >= lines.length - 1

  useEffect(() => {
    if (!isConfigured || isLastLine) onComplete?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConfigured, isLastLine])

  if (!isConfigured) {
    return <p className="text-sm text-neutral-400">Dialogue not configured yet.</p>
  }

  const currentLine = lines[Math.min(lineIndex, lines.length - 1)]
  const speakingCharacter = currentLine.speaker === 'LEFT' ? left : right

  function handleAdvance() {
    setLineIndex((index) => Math.min(index + 1, lines.length - 1))
  }

  // Large regardless of context (dominant/coverFill/plain admin preview) —
  // this is the slide's primary interactive content, not a supporting
  // media block, so it always claims most of the available space rather
  // than capping at the modest size other element types use.
  const outerClass = dominant ? 'flex h-full w-full items-center justify-center' : ''
  const boxClass = coverFill ? 'h-full w-full' : dominant ? 'aspect-video w-[90%] max-h-[90%]' : 'aspect-video w-[90%]'

  const node = (
    <button
      type="button"
      onClick={handleAdvance}
      disabled={isLastLine}
      className={`group relative block w-full overflow-hidden rounded-md bg-neutral-200 text-left ${boxClass} ${
        isLastLine ? 'cursor-default ring-2 ring-emerald-400' : 'cursor-pointer'
      }`}
    >
      <img src={scene.background_image} alt="" className="absolute inset-0 h-full w-full object-cover" />

      {/* Each character gets its own non-overlapping half of the stage,
          object-contain + object-bottom so a source illustration's own
          padding/aspect ratio never causes it to shrink away from its
          corner or overlap the other character. 85% of the scene's
          height, bottom-anchored, so the character reads as standing in
          the scene at a natural scale rather than towering over it. */}
      {left && (
        <div className="absolute bottom-0 left-0 h-[85%] w-1/2 p-2">
          <img
            src={left.avatar_image}
            alt={left.name}
            className={`h-full w-full object-contain object-bottom transition-opacity duration-300 ${
              currentLine.speaker === 'LEFT' ? 'opacity-100' : 'opacity-40'
            }`}
          />
        </div>
      )}
      {right && (
        <div className="absolute bottom-0 right-0 h-[85%] w-1/2 p-2">
          <img
            src={right.avatar_image}
            alt={right.name}
            className={`h-full w-full object-contain object-bottom transition-opacity duration-300 ${
              currentLine.speaker === 'RIGHT' ? 'opacity-100' : 'opacity-40'
            }`}
          />
        </div>
      )}

      <div className="absolute inset-x-4 bottom-4 rounded-lg bg-brand-navy/95 p-3 text-left shadow-lg">
        <p className="text-xs font-bold text-brand-gold">{speakingCharacter?.name ?? 'Speaker'}</p>
        <p className="mt-0.5 text-sm font-bold text-white">{currentLine.text}</p>
        {isLastLine ? (
          // Deliberately flat — no shadow, no gradient, no border — so it
          // reads as a status strip, not a button. An embossed/raised
          // treatment here was tried and rejected: it looked pressable, but
          // nothing happens if you tap it (this whole block sits inside the
          // dialogue's own, by-then-disabled <button>).
          <div className="mt-2 flex items-center justify-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-white">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Conversation is complete — click Next to continue to another slide
          </div>
        ) : (
          <p className="mt-1 text-right text-[10px] font-medium uppercase tracking-wide text-neutral-300">
            Click to continue
          </p>
        )}
      </div>
    </button>
  )

  return outerClass ? <div className={outerClass}>{node}</div> : node
}

interface ElementPreviewProps {
  element: SlideElement
  // Set only when a SlideTemplate is in effect (course or per-slide override)
  // — undefined leaves every element exactly as it rendered before templates
  // existed, so a slide with no template keeps its original appearance.
  textColor?: string
  accentColor?: string
  // Only set by SlideElementsView for the docked element in a two-column
  // (IMAGE_LEFT/IMAGE_RIGHT) layout. An IMAGE element there should read as
  // genuinely occupying its column rather than floating at its own intrinsic
  // size with empty space around it — `align` stops making sense once the
  // image fills the column, so this takes over sizing entirely for IMAGE.
  fill?: boolean
  // Set by SlideElementsView's fixed-canvas (student player) rendering only
  // — never by the admin preview. `coverFill` is the docked-column media in
  // IMAGE_LEFT/IMAGE_RIGHT, which now has a fixed, known column height (the
  // canvas's). For VIDEO_AUDIO this fills the column edge-to-edge; for IMAGE
  // it renders identically to `fill` below (contain, never cropped) — the
  // column div itself (SlideElementsView) paints a background matching the
  // slide's template/default so IMAGE's inevitable letterboxing blends in
  // rather than showing a gap. `dominant` is a STACKED slide whose only
  // element is a media one (e.g. a video with just a title) — it renders
  // large and centered instead of at its normal capped size, since there's
  // nothing else on the slide competing for space.
  coverFill?: boolean
  dominant?: boolean
  // DIALOGUE only — see DialogueBlock's onComplete. Unused (and harmless to
  // omit) everywhere else.
  onDialogueComplete?: (elementId: number) => void
}

// Shared read-only renderer for a Slide's elements — used by both the admin
// Slides tab (SlideCard preview) and the learner-facing course player, so
// content always looks identical in both places.
export function ElementPreview({
  element,
  textColor,
  accentColor,
  fill = false,
  coverFill = false,
  dominant = false,
  onDialogueComplete,
}: ElementPreviewProps) {
  switch (element.element_type) {
    case 'TEXT':
      return (
        <div
          className={`${QL_CONTENT_CLASS} w-full min-w-0 [overflow-wrap:anywhere] text-sm text-neutral-700 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol:last-child]:mb-0 [&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul:last-child]:mb-0`}
          style={{ color: textColor }}
          dangerouslySetInnerHTML={{ __html: richTextHtml(element.rich_text) }}
        />
      )

    case 'QUOTE':
      return (
        <div
          className={`${QL_CONTENT_CLASS} w-full min-w-0 [overflow-wrap:anywhere] border-l-2 border-brand-gold pl-3 text-sm text-neutral-700 italic [&_p]:mb-3 [&_p:last-child]:mb-0`}
          style={{ color: textColor, borderColor: accentColor }}
          dangerouslySetInnerHTML={{ __html: richTextHtml(element.rich_text) }}
        />
      )

    case 'IMAGE':
      if (!element.file) return <p className="text-sm text-neutral-400">No image uploaded yet.</p>
      if (dominant) {
        return (
          <figure className="flex h-full w-full flex-col items-center justify-center">
            <img src={element.file} alt={element.caption} className="max-h-[80%] max-w-[80%] rounded-md object-contain" />
            {element.caption && (
              <figcaption className="mt-2 text-xs text-neutral-500" style={{ color: textColor }}>
                {element.caption}
              </figcaption>
            )}
          </figure>
        )
      }
      if (coverFill) {
        // canvasMode (student player) docked IMAGE column only. h-full +
        // w-auto sizes the img purely from its own intrinsic aspect ratio
        // at this column's fixed height — no forced crop, no percentage
        // reserved width, it just renders at whatever width that ratio
        // produces. w-fit on the figure (not w-full) is what lets that
        // rendered width in turn become the *column's* width, in
        // SlideElementsView — this is the "hug" half of that; max-w-full
        // here is the "cap" half: normally a no-op (figure already hugs the
        // img exactly), but once the column hits its own max-width cap for
        // an unusually wide image, fit-content sizing shrinks figure to
        // that capped width for real, and *then* this max-w-full is what's
        // actually constraining — which, per the standard CSS
        // replaced-element sizing algorithm, makes the browser preserve the
        // image's ratio by shrinking its rendered height instead of its
        // width, i.e. exactly the letterboxed contain fallback the column
        // cap is there for. justify-start keeps the image's top edge
        // (not center) flush with the column's top, matching the text
        // column's first line, regardless of which of these two cases is
        // in play. Nothing here paints a background of its own — any
        // fallback letterbox space shows through to whatever background the
        // column div itself is painted with (SlideElementsView matches it
        // to the slide's template/default so it reads as a border, not a
        // gap).
        return (
          <figure className="flex h-full w-fit flex-col items-center justify-start">
            <img src={element.file} alt={element.caption} className="h-full w-auto max-w-full rounded-md" />
            {element.caption && (
              <figcaption className="mt-1 shrink-0 text-xs text-neutral-500" style={{ color: textColor }}>
                {element.caption}
              </figcaption>
            )}
          </figure>
        )
      }
      // Admin's flexible (non-canvas) split layout: bounded by the column's
      // width and its stretched height, but never forced to actually fill
      // that space — the img sizes itself with the classic replaced-element
      // auto-fit rule (max-width/max-height 100%, width/height auto)
      // instead of a fixed w-full/h-full box with object-fit, so the whole
      // image is always visible, never cropped, and centered rather than
      // top-aligned (SlideCard's column isn't a fixed height the way the
      // canvas's is, so there's no "line up with the text column's top
      // line" concern here the way there is for coverFill above).
      return fill ? (
        <figure className="flex h-full flex-col items-center justify-center">
          <img src={element.file} alt={element.caption} className="max-h-full max-w-full h-auto w-auto rounded-md" />
          {element.caption && (
            <figcaption className="mt-1 shrink-0 text-xs text-neutral-500" style={{ color: textColor }}>
              {element.caption}
            </figcaption>
          )}
        </figure>
      ) : (
        <figure className={`flex flex-col ${ALIGN_ITEMS_CLASS[element.align]}`}>
          <img src={element.file} alt={element.caption} className="max-h-64 rounded-md object-contain" />
          {element.caption && (
            <figcaption className="mt-1 text-xs text-neutral-500" style={{ color: textColor }}>
              {element.caption}
            </figcaption>
          )}
        </figure>
      )

    case 'VIDEO_AUDIO': {
      const embed = element.video_url ? resolveVideoEmbed(element.video_url) : null
      // dominant centers the (still-capped) media box in the space its
      // parent gives it; coverFill has no such wrapper since it's meant to
      // fill its column exactly, edge to edge, with nothing to center.
      const outerClass = dominant ? 'flex h-full w-full items-center justify-center' : ''
      const boxClass = coverFill ? 'h-full w-full' : dominant ? 'aspect-video w-[80%] max-h-[80%]' : 'aspect-video max-w-md'
      const videoClass = coverFill
        ? 'h-full w-full rounded-md object-cover'
        : dominant
          ? 'max-h-[80%] max-w-[80%] rounded-md'
          : 'max-w-md rounded-md'

      if (embed?.kind === 'embed') {
        const node = (
          <div className={boxClass}>
            <iframe src={embed.src} className="h-full w-full rounded-md" allowFullScreen title="Video" />
          </div>
        )
        return outerClass ? <div className={outerClass}>{node}</div> : node
      }
      if (element.video_file) {
        // controlsList/disablePictureInPicture/onContextMenu are a deterrent
        // only — they hide the browser's own "Download"/PiP affordances and
        // block the right-click "Save Video As" menu, but nothing stops a
        // determined user from grabbing the underlying src another way. The
        // real access control is server-side: video_file is already a
        // short-lived, per-user signed streaming URL, not a permanent public
        // file link — see courses.video_streaming (backend).
        const node = (
          <video
            controls
            controlsList="nodownload noremoteplayback"
            disablePictureInPicture
            onContextMenu={(e) => e.preventDefault()}
            src={element.video_file}
            className={videoClass}
          />
        )
        return outerClass ? <div className={outerClass}>{node}</div> : node
      }
      if (element.video_url) {
        return (
          <a
            href={element.video_url}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-brand-navy underline"
            style={{ color: accentColor }}
          >
            {element.video_url}
          </a>
        )
      }
      return <p className="text-sm text-neutral-400">No video or audio added yet.</p>
    }

    case 'BREAKOUT_IMAGE':
      return element.embed_url ? (
        <figure>
          <div className="aspect-video max-w-md">
            <iframe src={element.embed_url} className="h-full w-full rounded-md" title="Breakout image" />
          </div>
          {element.caption && (
            <figcaption className="mt-1 text-xs text-neutral-500" style={{ color: textColor }}>
              {element.caption}
            </figcaption>
          )}
        </figure>
      ) : (
        <p className="text-sm text-neutral-400">No embed set yet.</p>
      )

    case 'EMBED':
      return element.embed_url ? (
        <div className="aspect-video max-w-md">
          <iframe src={element.embed_url} className="h-full w-full rounded-md" title="Embed" />
        </div>
      ) : (
        <p className="text-sm text-neutral-400">No embed set yet.</p>
      )

    case 'DIALOGUE':
      return (
        <DialogueBlock
          element={element}
          dominant={dominant}
          coverFill={coverFill}
          onComplete={onDialogueComplete ? () => onDialogueComplete(element.id) : undefined}
        />
      )

    case 'FILE_DOWNLOAD':
    case 'PRESENTATION_PDF':
      return element.file ? (
        <a
          href={element.file}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-md border border-neutral-200 px-3 py-2 text-sm text-brand-navy hover:bg-neutral-50"
          style={{ color: accentColor }}
        >
          <FileDown className="h-4 w-4" />
          {element.caption || 'Download file'}
        </a>
      ) : (
        <p className="text-sm text-neutral-400">No file uploaded yet.</p>
      )

    default:
      return null
  }
}
