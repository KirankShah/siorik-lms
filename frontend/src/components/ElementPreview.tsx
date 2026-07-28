import { FileDown } from 'lucide-react'
import { resolveVideoEmbed } from '../lib/blocknote/videoProviders'
import type { ElementAlign, SlideElement } from '../types/slides'

const ALIGN_ITEMS_CLASS: Record<ElementAlign, string> = {
  LEFT: 'items-start',
  CENTER: 'items-center',
  RIGHT: 'items-end',
}

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
// paragraphs on either side — the intentional break all but disappears, and
// it does so identically everywhere this component is used (there's only
// one rendering path here, shared by every read-only view). Stripping these
// husks makes mb-3 the sole, deterministic source of paragraph spacing.
function stripEmptyParagraphs(html: string): string {
  return html.replace(/<p>(?:\s|&nbsp;|<br\s*\/?>)*<\/p>/gi, '')
}

function richTextHtml(richText: string): string {
  if (!richText) return '<span class="text-neutral-400">Empty</span>'
  return stripEmptyParagraphs(normalizeNonBreakingSpaces(richText))
}

// Shared read-only renderer for a Slide's elements — used by both the admin
// Slides tab (SlideCard preview) and the learner-facing course player, so
// content always looks identical in both places.
export function ElementPreview({ element }: { element: SlideElement }) {
  switch (element.element_type) {
    case 'TEXT':
      return (
        <div
          className="w-full min-w-0 [overflow-wrap:anywhere] text-sm text-neutral-700 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5"
          dangerouslySetInnerHTML={{ __html: richTextHtml(element.rich_text) }}
        />
      )

    case 'QUOTE':
      return (
        <div
          className="w-full min-w-0 [overflow-wrap:anywhere] border-l-2 border-brand-gold pl-3 text-sm text-neutral-700 italic [&_p]:mb-3 [&_p:last-child]:mb-0"
          dangerouslySetInnerHTML={{ __html: richTextHtml(element.rich_text) }}
        />
      )

    case 'IMAGE':
      return element.file ? (
        <figure className={`flex flex-col ${ALIGN_ITEMS_CLASS[element.align]}`}>
          <img src={element.file} alt={element.caption} className="max-h-64 rounded-md object-contain" />
          {element.caption && <figcaption className="mt-1 text-xs text-neutral-500">{element.caption}</figcaption>}
        </figure>
      ) : (
        <p className="text-sm text-neutral-400">No image uploaded yet.</p>
      )

    case 'VIDEO_AUDIO': {
      const embed = element.video_url ? resolveVideoEmbed(element.video_url) : null
      if (embed?.kind === 'embed') {
        return (
          <div className="aspect-video max-w-md">
            <iframe src={embed.src} className="h-full w-full rounded-md" allowFullScreen title="Video" />
          </div>
        )
      }
      if (element.video_file) {
        return <video controls src={element.video_file} className="max-w-md rounded-md" />
      }
      if (element.video_url) {
        return (
          <a href={element.video_url} target="_blank" rel="noreferrer" className="text-sm text-brand-navy underline">
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
          {element.caption && <figcaption className="mt-1 text-xs text-neutral-500">{element.caption}</figcaption>}
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

    case 'FILE_DOWNLOAD':
    case 'PRESENTATION_PDF':
      return element.file ? (
        <a
          href={element.file}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-md border border-neutral-200 px-3 py-2 text-sm text-brand-navy hover:bg-neutral-50"
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
