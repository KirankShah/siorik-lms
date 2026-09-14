import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Maximize, Minimize, ZoomIn, ZoomOut } from 'lucide-react'
import * as pdfjsLib from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import pdfjsWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { ContentProtectionBoundary } from '../components/player/ContentProtectionBoundary'
import { useAuth } from '../context/AuthContext'
import { fetchResource, fetchResourcePdfBlob } from '../lib/resourcesApi'
import type { Resource } from '../types/resources'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl

const MIN_SCALE = 0.6
const MAX_SCALE = 2.5
const SCALE_STEP = 0.2
const DEFAULT_SCALE = 1.2

// A small tiled PNG (data URL) drawn once per viewer session, repeated via
// CSS background over every page's canvas — this never touches the stored
// PDF file itself (it's pure client-side overlay), so the file at rest
// stays clean; only what's rendered on screen for *this* viewer carries it.
function buildWatermarkTileUrl(line1: string, line2: string): string {
  const canvas = document.createElement('canvas')
  canvas.width = 360
  canvas.height = 240
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''
  ctx.translate(canvas.width / 2, canvas.height / 2)
  ctx.rotate((-28 * Math.PI) / 180)
  ctx.textAlign = 'center'
  ctx.fillStyle = 'rgba(15, 23, 42, 0.09)'
  ctx.font = '600 16px system-ui, sans-serif'
  ctx.fillText(line1, 0, -6)
  ctx.font = '400 13px system-ui, sans-serif'
  ctx.fillText(line2, 0, 16)
  return canvas.toDataURL()
}

interface ResourcePageCanvasProps {
  page: PDFPageProxy
  scale: number
  watermarkUrl: string
}

function ResourcePageCanvas({ page, scale, watermarkUrl }: ResourcePageCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const viewport = page.getViewport({ scale })

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    canvas.width = viewport.width
    canvas.height = viewport.height
    const renderTask = page.render({ canvasContext: ctx, viewport })
    renderTask.promise.catch(() => {
      // Cancelled render tasks (e.g. a zoom change mid-render) reject —
      // nothing to surface, the next effect run renders the current state.
    })
    return () => renderTask.cancel()
  }, [page, viewport])

  return (
    <div
      className="relative mx-auto mb-4 bg-white shadow-md"
      style={{ width: viewport.width, height: viewport.height }}
    >
      <canvas ref={canvasRef} />
      <div
        className="pointer-events-none absolute inset-0"
        style={{ backgroundImage: `url(${watermarkUrl})`, backgroundRepeat: 'repeat' }}
      />
    </div>
  )
}

export function ResourceViewerPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const containerRef = useRef<HTMLDivElement>(null)

  const [resource, setResource] = useState<Resource | null>(null)
  const [pages, setPages] = useState<PDFPageProxy[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [scale, setScale] = useState(DEFAULT_SCALE)
  const [isFullscreen, setIsFullscreen] = useState(false)

  const watermarkUrl = useMemo(() => {
    if (!user) return ''
    const name = `${user.first_name} ${user.last_name}`.trim() || user.email
    return buildWatermarkTileUrl(name, user.email)
  }, [user])

  useEffect(() => {
    if (!id) return
    let cancelled = false
    let doc: PDFDocumentProxy | null = null

    fetchResource(Number(id))
      .then((r) => {
        if (!cancelled) setResource(r)
      })
      .catch(() => {
        if (!cancelled) setError('This resource is not available.')
      })

    fetchResourcePdfBlob(Number(id))
      .then((blob) => blob.arrayBuffer())
      .then((buffer) => pdfjsLib.getDocument({ data: buffer }).promise)
      .then(async (loadedDoc) => {
        if (cancelled) {
          void loadedDoc.destroy()
          return
        }
        doc = loadedDoc
        const loadedPages = await Promise.all(
          Array.from({ length: loadedDoc.numPages }, (_, i) => loadedDoc.getPage(i + 1)),
        )
        if (!cancelled) setPages(loadedPages)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load this document.')
      })

    return () => {
      cancelled = true
      void doc?.destroy()
    }
  }, [id])

  useEffect(() => {
    function handleFullscreenChange() {
      setIsFullscreen(document.fullscreenElement != null)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  function toggleFullscreen() {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    } else {
      void containerRef.current?.requestFullscreen()
    }
  }

  return (
    <ContentProtectionBoundary>
      <div ref={containerRef} className="flex h-screen flex-col bg-neutral-800">
        <div className="flex items-center justify-between gap-3 border-b border-white/10 bg-neutral-900 px-4 py-2 text-white">
          <p className="min-w-0 truncate text-sm font-medium">{resource?.title ?? 'Document'}</p>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setScale((s) => Math.max(MIN_SCALE, +(s - SCALE_STEP).toFixed(2)))}
              className="rounded p-1.5 hover:bg-white/10"
              aria-label="Zoom out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <span className="w-12 text-center text-xs tabular-nums">{Math.round(scale * 100)}%</span>
            <button
              type="button"
              onClick={() => setScale((s) => Math.min(MAX_SCALE, +(s + SCALE_STEP).toFixed(2)))}
              className="rounded p-1.5 hover:bg-white/10"
              aria-label="Zoom in"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={toggleFullscreen}
              className="ml-1 rounded p-1.5 hover:bg-white/10"
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
            >
              {isFullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto px-4 py-6">
          {error && <p className="text-center text-sm text-red-300">{error}</p>}
          {!error && !pages && <p className="text-center text-sm text-white/60">Loading document…</p>}
          {pages?.map((page, index) => (
            <ResourcePageCanvas key={index} page={page} scale={scale} watermarkUrl={watermarkUrl} />
          ))}
        </div>

        <p className="border-t border-white/10 bg-neutral-900 px-4 py-1.5 text-center text-[11px] text-white/40">
          This viewer deters casual downloading (no download/print controls, disabled right-click, an identifying
          watermark) — it is not an absolute technical guarantee against a determined, technically sophisticated
          user.
        </p>
      </div>
    </ContentProtectionBoundary>
  )
}
