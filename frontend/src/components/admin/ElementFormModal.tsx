import { useState } from 'react'
import { AlignCenter, AlignLeft, AlignRight } from 'lucide-react'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { RichTextField } from './RichTextField'
import { extractEmbedUrl } from '../../lib/embedUtils'
import { ELEMENT_TYPE_LABEL } from '../../lib/elementTypes'
import { resolveVideoEmbed } from '../../lib/blocknote/videoProviders'
import { isLowContrast } from '../../lib/colorContrast'
import { createElement, updateElement } from '../../lib/slidesApi'
import type { ElementInput } from '../../lib/slidesApi'
import type { ElementAlign, ElementType, SlideElement, SlideTemplate } from '../../types/slides'

// Pre-templates default look is a plain white card (see SlideElementsView) —
// used as the readability check's background when no template applies.
const DEFAULT_BACKGROUND_CSS = '#ffffff'

const ALIGN_OPTIONS: { value: ElementAlign; label: string; icon: typeof AlignLeft }[] = [
  { value: 'LEFT', label: 'Left', icon: AlignLeft },
  { value: 'CENTER', label: 'Center', icon: AlignCenter },
  { value: 'RIGHT', label: 'Right', icon: AlignRight },
]

interface ElementFormModalProps {
  slideId: number
  element: SlideElement | null
  elementType: ElementType
  nextOrder: number
  // The slide's effective template (course template or per-slide override) —
  // only used to warn if a chosen text/highlight color would be hard to read
  // against it. Omitted entirely means "no template", not "unknown".
  template?: SlideTemplate | null
  onSaved: () => void
  onClose: () => void
}

export function ElementFormModal({
  slideId,
  element,
  elementType,
  nextOrder,
  template = null,
  onSaved,
  onClose,
}: ElementFormModalProps) {
  const [richText, setRichText] = useState(element?.rich_text ?? '')
  const [caption, setCaption] = useState(element?.caption ?? '')
  const [align, setAlign] = useState<ElementAlign>(element?.align ?? 'CENTER')
  const [embedInput, setEmbedInput] = useState(element?.embed_url ?? '')
  const [videoMode, setVideoMode] = useState<'url' | 'upload'>(element?.video_file ? 'upload' : 'url')
  const [videoUrl, setVideoUrl] = useState(element?.video_url ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [colorWarning, setColorWarning] = useState<string | null>(null)

  function handleColorApplied(kind: 'color' | 'background', hex: string) {
    const backgroundCss = template?.background_css ?? DEFAULT_BACKGROUND_CSS
    if (!isLowContrast(hex, backgroundCss)) {
      setColorWarning(null)
      return
    }
    setColorWarning(
      `This ${kind === 'color' ? 'text' : 'highlight'} color may be hard to read against the current slide background.`,
    )
  }

  const videoPreview = videoMode === 'url' && videoUrl ? resolveVideoEmbed(videoUrl) : null

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    try {
      const payload: ElementInput = { slide: slideId, order: element?.order ?? nextOrder, element_type: elementType }

      if (elementType === 'TEXT' || elementType === 'QUOTE') {
        payload.rich_text = richText
      }
      if (elementType === 'IMAGE') {
        payload.caption = caption
        payload.align = align
        if (file) payload.file = file
      }
      if (elementType === 'VIDEO_AUDIO') {
        if (videoMode === 'url') {
          payload.video_url = videoUrl
        } else if (file) {
          payload.video_file = file
        }
      }
      if (elementType === 'BREAKOUT_IMAGE') {
        payload.embed_url = extractEmbedUrl(embedInput)
        payload.caption = caption
      }
      if (elementType === 'EMBED') {
        payload.embed_url = extractEmbedUrl(embedInput)
      }
      if (elementType === 'FILE_DOWNLOAD' || elementType === 'PRESENTATION_PDF') {
        payload.caption = caption
        if (file) payload.file = file
      }

      if (element) {
        await updateElement(element.id, payload)
      } else {
        await createElement(payload)
      }
      onSaved()
    } catch {
      setError('Could not save this element.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Modal
      title={`${element ? 'Edit' : 'Add'} ${ELEMENT_TYPE_LABEL[elementType]}`}
      onClose={onClose}
      // TEXT/QUOTE need real room: Quill's toolbar (bold/italic/underline/
      // strike, font, size, color, background, align, lists, indent, link,
      // clean) doesn't fit the default max-w-lg without cramming, which is
      // what was pushing the color/highlight swatch dropdowns (including the
      // white swatch) outside the modal's visible bounds.
      widthClassName={elementType === 'TEXT' || elementType === 'QUOTE' ? 'max-w-3xl' : undefined}
      maxHeightClassName={elementType === 'TEXT' || elementType === 'QUOTE' ? 'max-h-[92vh]' : undefined}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving…' : 'Save'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {(elementType === 'TEXT' || elementType === 'QUOTE') && (
          <div>
            <RichTextField
              key={element?.id ?? 'new'}
              initialHtml={richText}
              onChange={setRichText}
              onColorApplied={handleColorApplied}
              placeholder={elementType === 'QUOTE' ? 'Quote text…' : 'Text content…'}
              minHeight="480px"
            />
            {colorWarning && <p className="mt-1.5 text-xs text-amber-600">{colorWarning}</p>}
          </div>
        )}

        {elementType === 'IMAGE' && (
          <>
            <div>
              <label className="block text-sm font-medium text-neutral-700">Image</label>
              {element?.file && !file && (
                <img src={element.file} alt="" className="mt-2 max-h-40 rounded-md object-contain" />
              )}
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700">Caption (optional)</label>
              <input
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700">Alignment</label>
              <div className="mt-1 inline-flex rounded-md border border-neutral-300 p-0.5">
                {ALIGN_OPTIONS.map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setAlign(value)}
                    title={label}
                    aria-label={label}
                    className={`rounded px-2 py-1 transition ${
                      align === value ? 'bg-brand-navy text-white' : 'text-neutral-500 hover:bg-neutral-100'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {elementType === 'VIDEO_AUDIO' && (
          <>
            <div className="flex gap-4 text-sm">
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={videoMode === 'url'} onChange={() => setVideoMode('url')} />
                Paste a URL
              </label>
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={videoMode === 'upload'} onChange={() => setVideoMode('upload')} />
                Upload a file
              </label>
            </div>

            {videoMode === 'url' ? (
              <div>
                <label className="block text-sm font-medium text-neutral-700">YouTube, Vimeo, or Loom URL</label>
                <input
                  value={videoUrl}
                  onChange={(e) => setVideoUrl(e.target.value)}
                  placeholder="https://…"
                  className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
                />
                {videoPreview?.kind === 'embed' && (
                  <div className="mt-3 aspect-video max-w-sm">
                    <iframe src={videoPreview.src} className="h-full w-full rounded-md" allowFullScreen title="Preview" />
                  </div>
                )}
                {videoPreview?.kind === 'file' && (
                  <p className="mt-2 text-xs text-neutral-500">
                    No provider detected — this will link directly instead of embedding.
                  </p>
                )}
              </div>
            ) : (
              <div>
                <label className="block text-sm font-medium text-neutral-700">Video or audio file</label>
                {element?.video_file && !file && (
                  <p className="mt-1 text-xs text-neutral-500">Current file: {element.video_file.split('/').pop()}</p>
                )}
                <input
                  type="file"
                  accept="video/*,audio/*"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="mt-1 text-sm"
                />
              </div>
            )}
          </>
        )}

        {(elementType === 'BREAKOUT_IMAGE' || elementType === 'EMBED') && (
          <>
            <div>
              <label className="block text-sm font-medium text-neutral-700">URL or iframe embed code</label>
              <textarea
                value={embedInput}
                onChange={(e) => setEmbedInput(e.target.value)}
                rows={3}
                placeholder='https://… or <iframe src="…"></iframe>'
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 font-mono text-xs"
              />
            </div>
            {elementType === 'BREAKOUT_IMAGE' && (
              <div>
                <label className="block text-sm font-medium text-neutral-700">Caption (optional)</label>
                <input
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
                />
              </div>
            )}
          </>
        )}

        {(elementType === 'FILE_DOWNLOAD' || elementType === 'PRESENTATION_PDF') && (
          <>
            <div>
              <label className="block text-sm font-medium text-neutral-700">File</label>
              {element?.file && !file && (
                <p className="mt-1 text-xs text-neutral-500">Current file: {element.file.split('/').pop()}</p>
              )}
              <input
                type="file"
                accept={elementType === 'PRESENTATION_PDF' ? '.pdf,.ppt,.pptx' : undefined}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700">Label</label>
              <input
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="What learners see on the download button"
                className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
              />
            </div>
          </>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </Modal>
  )
}
