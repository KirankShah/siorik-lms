import type { AuthTokens } from '../types/auth'

const ACCESS_TOKEN_KEY = 'lms_access_token'
const REFRESH_TOKEN_KEY = 'lms_refresh_token'

// Tradeoff: tokens are kept in localStorage for simplicity (easy to read/write
// from plain JS, survives tab refreshes, no extra backend cookie plumbing).
// The cost is XSS exposure — any script that runs on this origin (e.g. from a
// compromised dependency) can read localStorage and steal both tokens. A
// production hardening pass would move the refresh token (at least) into an
// httpOnly, Secure, SameSite cookie set by the backend so client-side JS can
// never read it, and keep only the short-lived access token in memory.

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(tokens: AuthTokens): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access)
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh)
}

export function setAccessToken(access: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, access)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}
