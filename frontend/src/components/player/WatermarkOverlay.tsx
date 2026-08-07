import { useAuth } from '../../context/AuthContext'

function escapeForSvgText(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function buildWatermarkPattern(label: string): string {
  const safeLabel = escapeForSvgText(label)
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="340" height="220">' +
    '<text x="170" y="110" transform="rotate(-25 170 110)" text-anchor="middle" ' +
    `font-family="sans-serif" font-size="13" fill="rgba(0,0,0,0.16)">${safeLabel}</text>` +
    '</svg>'
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`
}

// Traceability, not prevention: if this content is screenshotted or
// screen-recorded — something no browser API can detect or block, see
// ContentProtectionBoundary — the tiled watermark ties a leak back to
// whichever learner's session rendered it. Purely visual: pointer-events
// are disabled so it never intercepts clicks/drags on the content beneath
// (video controls, drag-and-drop question types, etc.).
export function WatermarkOverlay() {
  const { user } = useAuth()
  if (!user) return null

  const name = `${user.first_name} ${user.last_name}`.trim() || user.email

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-10 select-none"
      style={{ backgroundImage: buildWatermarkPattern(`${name} · ${user.email}`), backgroundRepeat: 'repeat' }}
    />
  )
}
