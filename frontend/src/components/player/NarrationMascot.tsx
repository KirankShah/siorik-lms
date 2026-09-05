import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import greetingHappy from '../../assets/greeting-happy.png'
import mascotIdle from '../../assets/greeting-neutral.png'
import { NarrationPlayer } from './NarrationPlayer'
import type { SlideNarration } from '../../types/narration'
import type { SlideTemplate } from '../../types/slides'

interface NarrationMascotProps {
  slideId: number
  narrations: SlideNarration[]
  // The slide's active template (course template, or its own override) —
  // drives the badge's adaptive contrast. See isLightHexColor below.
  template: SlideTemplate | null
}

const BUBBLE_AUTO_DISMISS_MS = 5000
const PEEK_MIN_DELAY_MS = 15000
const PEEK_MAX_DELAY_MS = 20000
const PEEK_DURATION_MS = 700

// Perceived-brightness split (ITU-R BT.601) on a #rrggbb string — true above
// the midpoint means "light color". Used on SlideTemplate.text_color: a
// template only picks a light text_color when its own background is dark
// (see the seed data's own comment: "chosen for legible contrast against
// background_css"), so this is a reliable, no-extra-fetch proxy for
// light-vs-dark background without parsing background_css itself.
function isLightHexColor(hex: string): boolean {
  const clean = hex.replace('#', '')
  if (clean.length !== 6) return false
  const r = parseInt(clean.slice(0, 2), 16)
  const g = parseInt(clean.slice(2, 4), 16)
  const b = parseInt(clean.slice(4, 6), 16)
  if ([r, g, b].some(Number.isNaN)) return false
  return (r * 299 + g * 587 + b * 114) / 1000 > 150
}

// Floating, mascot-triggered entry point to the narration player (Part 3) —
// fixed-position so it never shifts other slide content and is unaffected
// by the fullscreen overlay's clipped, non-scrolling content well. Visible
// only on CONTENT slides with at least one SlideNarration (ContentSlidePlayer
// only renders this when narrations is non-empty).
export function NarrationMascot({ slideId, narrations, template }: NarrationMascotProps) {
  const [bubbleVisible, setBubbleVisible] = useState(true)
  const [panelOpen, setPanelOpen] = useState(false)
  const [hasOpenedPanel, setHasOpenedPanel] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isPeeking, setIsPeeking] = useState(false)

  const bubbleVisibleRef = useRef(bubbleVisible)
  const panelOpenRef = useRef(panelOpen)
  const isPlayingRef = useRef(isPlaying)
  bubbleVisibleRef.current = bubbleVisible
  panelOpenRef.current = panelOpen
  isPlayingRef.current = isPlaying

  // A fresh slide load: greet, then auto-dismiss into the small persistent icon.
  useEffect(() => {
    setBubbleVisible(true)
    setPanelOpen(false)
    setHasOpenedPanel(false)
    setIsPlaying(false)
    const timer = window.setTimeout(() => setBubbleVisible(false), BUBBLE_AUTO_DISMISS_MS)
    return () => window.clearTimeout(timer)
  }, [slideId])

  // Idle peek every 15-20s, skipped (and rescheduled) whenever the bubble is
  // showing, the panel is open, or audio is playing — checked at fire time
  // via refs so this scheduling loop doesn't need to restart on every state
  // change, just on slide change.
  useEffect(() => {
    let timeoutId: number
    function scheduleNext() {
      const delay = PEEK_MIN_DELAY_MS + Math.random() * (PEEK_MAX_DELAY_MS - PEEK_MIN_DELAY_MS)
      timeoutId = window.setTimeout(() => {
        if (!bubbleVisibleRef.current && !panelOpenRef.current && !isPlayingRef.current) {
          setIsPeeking(true)
          window.setTimeout(() => setIsPeeking(false), PEEK_DURATION_MS)
        }
        scheduleNext()
      }, delay)
    }
    scheduleNext()
    return () => window.clearTimeout(timeoutId)
  }, [slideId])

  function handleMascotClick() {
    setBubbleVisible(false)
    setHasOpenedPanel(true)
    setPanelOpen((v) => !v)
  }

  const isDarkBackgroundTemplate = template ? isLightHexColor(template.text_color) : false
  const badgeClass = isDarkBackgroundTemplate ? 'bg-amber-50' : 'bg-brand-navy'

  return (
    <div className="no-print fixed right-6 bottom-6 z-[110] flex flex-col items-end gap-2">
      {bubbleVisible && !panelOpen && (
        <div className="max-w-56 rounded-2xl rounded-br-sm border border-neutral-200 bg-white px-3 py-2 text-xs text-neutral-700 shadow-lg">
          Feeling bored or confused? I can explain this in simple terms!
        </div>
      )}

      {hasOpenedPanel && (
        <div className={`w-80 max-w-[85vw] rounded-lg border border-neutral-200 bg-white shadow-xl ${panelOpen ? '' : 'hidden'}`}>
          <div className="flex items-center justify-between border-b border-neutral-100 px-3 py-2">
            <span className="text-xs font-semibold text-neutral-700">Narration</span>
            <button
              type="button"
              onClick={() => setPanelOpen(false)}
              aria-label="Close narration player"
              className="text-neutral-400 transition hover:text-neutral-700"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="p-3">
            <NarrationPlayer narrations={narrations} onPlayingChange={setIsPlaying} />
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={handleMascotClick}
        aria-label={panelOpen ? 'Close narration helper' : 'Open narration helper'}
        className="relative flex h-14 w-14 items-center justify-center"
      >
        <span className={`absolute inset-0 rounded-full border-2 border-brand-gold shadow-md ${badgeClass}`} />
        <img
          src={bubbleVisible ? greetingHappy : mascotIdle}
          alt=""
          className={`relative h-10 w-10 object-contain ${isPeeking ? 'mascot-peek' : ''}`}
        />
      </button>
    </div>
  )
}
