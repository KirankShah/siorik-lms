import type { AuthTokens } from '../types/auth'
import { clearTokens, getAccessToken, getRefreshToken, setAccessToken } from './tokenStorage'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API request failed with status ${status}`)
    this.status = status
    this.body = body
  }
}

// Called whenever a refresh attempt fails (refresh token missing/expired/invalid).
// AuthContext subscribes to this so it can clear user state and redirect to /login.
let onSessionExpired: (() => void) | null = null

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler
}

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken()
  if (!refresh) return null

  // Coalesce concurrent refresh attempts into a single in-flight request.
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        if (!response.ok) return null
        const data = (await response.json()) as { access: string }
        setAccessToken(data.access)
        return data.access
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  skipAuth?: boolean
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuth, body, headers, ...rest } = options

  const doFetch = async (): Promise<Response> => {
    const requestHeaders = new Headers(headers)
    if (body !== undefined && !requestHeaders.has('Content-Type')) {
      requestHeaders.set('Content-Type', 'application/json')
    }
    if (!skipAuth) {
      const access = getAccessToken()
      if (access) requestHeaders.set('Authorization', `Bearer ${access}`)
    }
    return fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  }

  let response = await doFetch()

  if (response.status === 401 && !skipAuth) {
    const newAccess = await refreshAccessToken()
    if (newAccess) {
      response = await doFetch()
    } else {
      clearTokens()
      onSessionExpired?.()
    }
  }

  if (!response.ok) {
    let errorBody: unknown = null
    try {
      errorBody = await response.json()
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, errorBody)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function login(email: string, password: string): Promise<AuthTokens> {
  return apiFetch<AuthTokens>('/auth/login/', {
    method: 'POST',
    body: { email, password },
    skipAuth: true,
  })
}
