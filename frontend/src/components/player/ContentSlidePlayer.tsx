import { useEffect, useState } from 'react'
import { Download, Maximize } from 'lucide-react'
import { SlideCanvas } from './SlideCanvas'
import { SlideElementsView } from '../SlideElementsView'
import { Button } from '../ui/Button'
import { fetchElements } from '../../lib/slidesApi'
import { fetchSlideTemplates } from '../../lib/slideTemplatesApi'
import type { SlideElement, SlideSummary, SlideTemplate } from '../../types/slides'

interface ContentSlidePlayerProps {
  slide: SlideSummary
  // The course's current template — null if none is set. A slide only
  // deviates from this via its own template_override.
  courseTemplateId: number | null
  onEnterFullscreen?: () => void
  isFullscreen?: boolean
}

export function ContentSlidePlayer({
  slide,
  courseTemplateId,
  onEnterFullscreen,
  isFullscreen = false,
}: ContentSlidePlayerProps) {
  const [elements, setElements] = useState<SlideElement[] | null>(null)
  const [templates, setTemplates] = useState<SlideTemplate[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setElements(null)
    fetchElements(slide.id)
      .then(setElements)
      .catch(() => setError('Could not load this slide’s content.'))
  }, [slide.id])

  const effectiveTemplateId = slide.template_override ?? courseTemplateId

  useEffect(() => {
    if (effectiveTemplateId === null) return
    fetchSlideTemplates().then(setTemplates).catch(() => {})
  }, [effectiveTemplateId])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!elements) return <p className="text-sm text-neutral-500">Loading…</p>

  const template = effectiveTemplateId === null ? null : (templates.find((t) => t.id === effectiveTemplateId) ?? null)

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
        <SlideCanvas fullscreen={isFullscreen}>
          <SlideElementsView
            elements={elements}
            layout={slide.layout}
            template={template}
            title={slide.title || `Slide ${slide.order}`}
            canvasMode
            imageColumnWidth={slide.image_column_width}
          />
        </SlideCanvas>
      </div>
    </div>
  )
}
