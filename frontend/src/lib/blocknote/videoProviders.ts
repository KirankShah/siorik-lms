export type VideoEmbed = { kind: 'embed'; provider: string; src: string } | { kind: 'file'; src: string } | null

// Detects YouTube/Vimeo/Wistia/Loom links and rewrites them to their embed
// URL. Anything else (including our own uploaded storage URLs) falls back to
// plain <video> playback.
export function resolveVideoEmbed(url: string): VideoEmbed {
  if (!url) return null

  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return { kind: 'file', src: url }
  }

  const host = parsed.hostname.replace(/^www\./, '')

  if (host === 'youtube.com' || host === 'm.youtube.com') {
    const id = parsed.pathname.startsWith('/shorts/')
      ? parsed.pathname.split('/')[2]
      : parsed.searchParams.get('v')
    if (id) return { kind: 'embed', provider: 'YouTube', src: `https://www.youtube.com/embed/${id}` }
  }

  if (host === 'youtu.be') {
    const id = parsed.pathname.slice(1)
    if (id) return { kind: 'embed', provider: 'YouTube', src: `https://www.youtube.com/embed/${id}` }
  }

  if (host === 'vimeo.com') {
    const id = parsed.pathname.split('/').filter(Boolean).pop()
    if (id && /^\d+$/.test(id)) return { kind: 'embed', provider: 'Vimeo', src: `https://player.vimeo.com/video/${id}` }
  }

  if (host.endsWith('wistia.com') || host === 'wi.st') {
    // Matches /medias/<id> or /embed/iframe/<id>
    const match = parsed.pathname.match(/(?:medias|iframe)\/([a-zA-Z0-9]+)/)
    if (match) return { kind: 'embed', provider: 'Wistia', src: `https://fast.wistia.net/embed/iframe/${match[1]}` }
  }

  if (host === 'loom.com') {
    const match = parsed.pathname.match(/\/(?:share|embed)\/([a-zA-Z0-9]+)/)
    if (match) return { kind: 'embed', provider: 'Loom', src: `https://www.loom.com/embed/${match[1]}` }
  }

  return { kind: 'file', src: url }
}
