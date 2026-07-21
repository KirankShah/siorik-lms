interface JwtPayload {
  exp?: number
  [key: string]: unknown
}

// Decodes the payload of a JWT without verifying its signature — used only to
// read the `exp` claim client-side for scheduling a proactive refresh. The
// server is the source of truth for actually validating the token.
export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const [, payload] = token.split('.')
    if (!payload) return null
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json) as JwtPayload
  } catch {
    return null
  }
}

export function getTokenExpiryMs(token: string): number | null {
  const payload = decodeJwtPayload(token)
  if (!payload?.exp) return null
  return payload.exp * 1000
}
