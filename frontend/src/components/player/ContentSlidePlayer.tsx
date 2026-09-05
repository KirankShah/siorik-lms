import { useEffect, useState } from 'react'
import { Download, Maximize } from 'lucide-react'
import { NARRATION_BAR_FULLSCREEN_RESERVE_PX, NarrationPlayer } from './NarrationPlayer'
import { SlideCanvas } from './SlideCanvas'
import { SlideElementsView } from '../SlideElementsView'
import { Button } from '../ui/Button'
import { fetchNarrationsForSlide } from '../../lib/narrationApi'
import { fetchElements } from '../../lib/slidesApi'
import { fetchSlideTemplates } from '../../lib/slideTemplatesApi'
import type { SlideNarration } from '../../types/narration'
import type { SlideElement, SlideSummary, SlideTemplate } from '../../types/slides'

interface ContentSlidePlayerProps {
  slide: SlideSummary
  // The course's current template — null if none is set. A slide only
  // deviates from this via its own template_override.
  courseTemplateId: number | null
  onEnterFullscreen?: () => void
  isFullscreen?: boolean
  // Fired whenever the slide's Dialogue-completion state changes — see
  // SlidePlayer, which folds this into the Next-button gate alongside the
  // dwell timer. Not called at all until elements have loaded, so a slide
  // with no Dialogue element never touches the caller's gate (SlidePlayer
  // defaults it to satisfied). Once elements are known, it's
  // `true` whenever every DIALOGUE element on the slide has reached its
  // final line (vacuously true if there are none).
  onDialogueGateChange?: (satisfied: boolean) => void
}

export function ContentSlidePlayer({
  slide,
  courseTemplateId,
  onEnterFullscreen,
  isFullscreen = false,
  onDialogueGateChange,
}: ContentSlidePlayerProps) {
  const [elements, setElements] = useState<SlideElement[] | null>(null)
  const [templates, setTemplates] = useState<SlideTemplate[]>([])
  const [narrations, setNarrations] = useState<SlideNarration[]>([])
  const [error, setError] = useState<string | null>(null)
  const [completedDialogueIds, setCompletedDialogueIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    setElements(null)
    setCompletedDialogueIds(new Set())
    fetchElements(slide.id)
      .then(setElements)
      .catch(() => setError('Could not load this slide’s content.'))
  }, [slide.id])

  // Narration is a supplementary aid, not core slide content — a failure to
  // load it should never block or error out the slide itself.
  useEffect(() => {
    setNarrations([])
    fetchNarrationsForSlide(slide.id)
      .then(setNarrations)
      .catch(() => {})
  }, [slide.id])

  useEffect(() => {
    if (!elements) return
    const dialogueElementIds = elements.filter((e) => e.element_type === 'DIALOGUE').map((e) => e.id)
    onDialogueGateChange?.(dialogueElementIds.every((id) => completedDialogueIds.has(id)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elements, completedDialogueIds])

  function handleDialogueComplete(elementId: number) {
    setCompletedDialogueIds((prev) => (prev.has(elementId) ? prev : new Set(prev).add(elementId)))
  }

  const effectiveTemplateId = slide.template_override ?? courseTemplateId

  useEffect(() => {
    if (effectiveTemplateId === null) return
    fetchSlideTemplates().then(setTemplates).catch(() => {})
  }, [effectiveTemplateId])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!elements) return <p className="text-sm text-neutral-500">Loading…</p>

  const template = effectiveTemplateId === null ? null : (templates.find((t) => t.id === effectiveTemplateId) ?? null)
  const hasNarration = narrations.length > 0

  return (
    <div className={isFullscreen ? 'flex h-full flex-col' : ''}>
      {!isFullscreen && (
        <div className="no-print mb-4 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <Download className="h-4 w-4" />
            Download as PDF
          </Button>
          {onEnterFullscreen && (
            <Button variant="outline" size="sm" onClick={onEnterFullscreen}>
              <Maximize className="h-4 w-4" />
              Fullscreen
            </Button>
          )}
        </div>
      )}

      {/* print-target stays on this outer div so "Download as PDF" still
          isolates exactly this subtree — see index.css's @media print block,
          which also resets the fixed-canvas sizing/scroll/crop below so the
          PDF gets full flowing content instead of a clipped 16:9 snapshot. */}
      <div className={`print-target w-full ${isFullscreen ? 'min-h-0 flex-1' : ''}`}>
        <SlideCanvas
          fullscreen={isFullscreen}
          bottomInsetPx={isFullscreen && hasNarration ? NARRATION_BAR_FULLSCREEN_RESERVE_PX : 0}
        >
          <SlideElementsView
            elements={elements}
            layout={slide.layout}
            template={template}
            title={slide.title || `Slide ${slide.order}`}
            canvasMode
            imageColumnWidth={slide.image_column_width}
            onDialogueComplete={handleDialogueComplete}
          />
        </SlideCanvas>
      </div>

      {/* Supplementary aid — never touches SlidePlayer's dwell timer or
          completion gating. Rendered here (not inside SlideCanvas/
          SlideElementsView) so it never becomes part of the PDF export and
          never overlaps slide content, but still renders through this same
          ContentSlidePlayer tree the standard and fullscreen views both
          already share (see CourseDetailPage's single slidePlayerNode). */}
      {hasNarration && (
        <div className={`no-print mx-auto w-full max-w-3xl ${isFullscreen ? 'mt-2 shrink-0' : 'mt-4'}`}>
          <NarrationPlayer narrations={narrations} />
        </div>
      )}
    </div>
  )
}
