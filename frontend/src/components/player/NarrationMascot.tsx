import { useEffect, useRef, useState } from 'react'
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
const GREETING_TEXT = 'Feeling bored or confused? I can explain this in simple terms!'
const HOVER_TEXT = "Want me to summarize or explain this in simple terms — no need to read through it all?"

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

// Floating, mascot-triggered entry point to the narration player — just the
// icon/badge/speech-bubble; the player itself is a Modal (NarrationPlayer),
// not a docked panel, so it never competes with the mascot or slide content
// for layout space. Fixed-position so it never shifts other slide content
// and is unaffected by the fullscreen overlay's clipped, non-scrolling
// content well. Visible only on CONTENT slides with at least one
// SlideNarration (ContentSlidePlayer only renders this when narrations is
// non-empty).
export function NarrationMascot({ slideId, narrations, template }: NarrationMascotProps) {
  const [bubbleVisible, setBubbleVisible] = useState(true)
  const [panelOpen, setPanelOpen] = useState(false)
  const [isPeeking, setIsPeeking] = useState(false)
  const [isHovering, setIsHovering] = useState(false)

  const bubbleVisibleRef = useRef(bubbleVisible)
  const panelOpenRef = useRef(panelOpen)
  const isHoveringRef = useRef(isHovering)
  bubbleVisibleRef.current = bubbleVisible
  panelOpenRef.current = panelOpen
  isHoveringRef.current = isHovering

  // A fresh slide load: greet, then auto-dismiss into the small persistent icon.
  useEffect(() => {
    setBubbleVisible(true)
    setPanelOpen(false)
    const timer = window.setTimeout(() => setBubbleVisible(false), BUBBLE_AUTO_DISMISS_MS)
    return () => window.clearTimeout(timer)
  }, [slideId])

  // Idle peek every 15-20s, skipped (and rescheduled) whenever the bubble is
  // showing (greeting or hover) or the panel is open — the panel can only
  // ever be open while audio might be playing (NarrationPlayer unmounts,
  // stopping playback, whenever it closes), so gating on panelOpen alone
  // covers "audio playing" too. Checked at fire time via refs so this
  // scheduling loop doesn't need to restart on every state change, just on
  // slide change.
  useEffect(() => {
    let timeoutId: number
    function scheduleNext() {
      const delay = PEEK_MIN_DELAY_MS + Math.random() * (PEEK_MAX_DELAY_MS - PEEK_MIN_DELAY_MS)
      timeoutId = window.setTimeout(() => {
        if (!bubbleVisibleRef.current && !panelOpenRef.current && !isHoveringRef.current) {
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
    setPanelOpen((v) => !v)
  }

  const isDarkBackgroundTemplate = template ? isLightHexColor(template.text_color) : false
  const badgeClass = isDarkBackgroundTemplate ? 'bg-amber-50' : 'bg-brand-navy'
  // A gentle continuous bob keeps the mascot visibly "alive" — separate from
  // the bigger periodic peek above, which stays a rare, more deliberate
  // attention-grab. Paused while the panel is open or being hovered so it
  // isn't distracting once it already has the learner's attention;
  // combining it with the peek transform would fight that animation, so it
  // steps aside whenever a peek is in progress.
  const isBobbing = !panelOpen && !isPeeking && !isHovering
  // The auto-greeting takes priority over the hover prompt if both are
  // somehow true at once (hovering during the first few seconds on a fresh
  // slide) — once the greeting's own auto-dismiss timer clears it, hovering
  // takes over as the way to bring the bubble back.
  const showBubble = !panelOpen && (bubbleVisible || isHovering)
  const bubbleText = bubbleVisible ? GREETING_TEXT : HOVER_TEXT

  return (
    // Vertically centered on the right edge rather than pinned to the
    // bottom corner — anchoring to the bottom put it directly over the
    // Next button, which SlideNavFooter (standard view) and
    // FullscreenSlideOverlay's own nav bar both right-align at the bottom
    // of their respective views. Centering vertically clears both
    // unconditionally instead of needing to know either footer's exact height.
    <div className="no-print fixed top-1/2 right-6 z-[110] -translate-y-1/2">
      <div
        className="relative"
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
      >
        {showBubble && (
          <div className="absolute right-0 bottom-full mb-4 max-w-80 rounded-2xl rounded-br-sm border border-neutral-200 bg-white px-4 py-3 text-sm leading-snug text-neutral-700 shadow-xl">
            {bubbleText}
          </div>
        )}

        <button
          type="button"
          onClick={handleMascotClick}
          aria-label={panelOpen ? 'Close narration helper' : 'Open narration helper'}
          className="relative flex h-40 w-40 items-center justify-center"
        >
          <span className={`absolute inset-0 rounded-full border-2 border-brand-gold shadow-lg ${badgeClass}`} />
          <img
            src={bubbleVisible ? greetingHappy : mascotIdle}
            alt=""
            className={`relative h-32 w-32 object-contain ${isPeeking ? 'mascot-peek' : isBobbing ? 'mascot-idle-bob' : ''}`}
          />
        </button>
      </div>

      {panelOpen && <NarrationPlayer narrations={narrations} onClose={() => setPanelOpen(false)} />}
    </div>
  )
}
