import { useEffect, useState } from 'react'
import { Download, Maximize } from 'lucide-react'
import { ElementPreview } from '../ElementPreview'
import { Button } from '../ui/Button'
import { fetchElements } from '../../lib/slidesApi'
import type { SlideElement, SlideSummary } from '../../types/slides'

interface ContentSlidePlayerProps {
  slide: SlideSummary
  onEnterFullscreen?: () => void
  isFullscreen?: boolean
}

export function ContentSlidePlayer({ slide, onEnterFullscreen, isFullscreen = false }: ContentSlidePlayerProps) {
  const [elements, setElements] = useState<SlideElement[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setElements(null)
    fetchElements(slide.id)
      .then(setElements)
      .catch(() => setError('Could not load this slide’s content.'))
  }, [slide.id])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!elements) return <p className="text-sm text-neutral-500">Loading…</p>

  return (
    <div>
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

      {/* No nested card chrome here — the outer <Card> in CourseDetailPage
          already provides the white box/border/padding. Rendering another
          bordered box around this content (as before) doubled the padding
          and let the two boxes disagree on height. Text stays capped to a
          comfortable reading width; the card itself sizes purely to
          whatever this slide actually contains. */}
      <div className="print-target max-w-3xl space-y-6">
        <h1 className="text-lg font-semibold text-neutral-900">{slide.title || `Slide ${slide.order}`}</h1>
        {elements.length === 0 ? (
          <p className="text-sm text-neutral-400">This slide has no content yet.</p>
        ) : (
          elements.map((element) => <ElementPreview key={element.id} element={element} />)
        )}
      </div>
    </div>
  )
}
