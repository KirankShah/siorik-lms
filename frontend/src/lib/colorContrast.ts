// Lightweight readability nudge for the slide-template color pickers — not a
// full WCAG audit. Uses the standard sRGB relative-luminance formula (the
// same math WCAG contrast ratios are built on) but stops at a single "is
// this roughly readable" ratio rather than distinguishing AA/AAA, large vs.
// normal text, etc.

const HEX_RE = /#[0-9a-f]{3,8}/gi

function hexToRgb(hex: string): [number, number, number] | null {
  let h = hex.replace('#', '')
  if (h.length === 3) {
    h = h
      .split('')
      .map((c) => c + c)
      .join('')
  }
  if (h.length !== 6) return null
  const num = Number.parseInt(h, 16)
  if (Number.isNaN(num)) return null
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255]
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs
}

function contrastRatio(hexA: string, hexB: string): number | null {
  const rgbA = hexToRgb(hexA)
  const rgbB = hexToRgb(hexB)
  if (!rgbA || !rgbB) return null
  const [l1, l2] = [relativeLuminance(rgbA), relativeLuminance(rgbB)].sort((a, b) => b - a)
  return (l1 + 0.05) / (l2 + 0.05)
}

// Below this, text is flagged as "may be hard to read". Deliberately looser
// than WCAG AA's 4.5:1 (normal text) since this is a non-blocking nudge, not
// a compliance gate — it's meant to catch clearly bad picks like white text
// on a near-white background, not every borderline combination.
const LOW_CONTRAST_THRESHOLD = 3

// `backgroundCss` can be a plain hex or a multi-stop gradient (see
// SlideTemplate.background_css) — every hex stop is checked and the worst
// (lowest) contrast ratio wins, so a warning fires if `color` would be hard
// to read against any part of the gradient. Returns null if either color
// can't be parsed (nothing to compare).
export function isLowContrast(color: string, backgroundCss: string): boolean {
  const stops = backgroundCss.match(HEX_RE)
  if (!stops || stops.length === 0) return false
  const ratios = stops.map((stop) => contrastRatio(color, stop)).filter((r): r is number => r !== null)
  if (ratios.length === 0) return false
  return Math.min(...ratios) < LOW_CONTRAST_THRESHOLD
}
