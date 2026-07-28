// The Embed/Breakout-image fields accept either a bare URL or a pasted
// <iframe> snippet, but the backend stores a single URLField — pull the src
// out of iframe code so either input shape ends up valid either way.
export function extractEmbedUrl(input: string): string {
  const trimmed = input.trim()
  const iframeMatch = trimmed.match(/<iframe[^>]*\ssrc=["']([^"']+)["']/i)
  if (iframeMatch) return iframeMatch[1]
  return trimmed
}
