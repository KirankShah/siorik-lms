import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { apiFetch, login as loginRequest, setSessionExpiredHandler } from '../lib/apiClient'
import { getTokenExpiryMs } from '../lib/jwt'
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../lib/tokenStorage'
import type { User } from '../types/auth'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

// Refresh this many ms before the access token actually expires, so a
// request made right before expiry doesn't race a still-in-flight refresh.
const REFRESH_MARGIN_MS = 60_000

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimer.current) {
      clearTimeout(refreshTimer.current)
      refreshTimer.current = null
    }
  }, [])

  const scheduleRefresh = useCallback((accessToken: string) => {
    clearRefreshTimer()
    const expiryMs = getTokenExpiryMs(accessToken)
    if (!expiryMs) return

    const delay = Math.max(expiryMs - Date.now() - REFRESH_MARGIN_MS, 5_000)
    refreshTimer.current = setTimeout(async () => {
      const refresh = getRefreshToken()
      if (!refresh) return
      try {
        const data = await apiFetch<{ access: string }>('/auth/refresh/', {
          method: 'POST',
          body: { refresh },
          skipAuth: true,
        })
        setTokens({ access: data.access, refresh })
        scheduleRefresh(data.access)
      } catch {
        // Refresh failed; apiClient's 401 handling on the next request (or
        // the session-expired handler below) will finish logging the user out.
      }
    }, delay)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clearRefreshTimer])

  const logout = useCallback(() => {
    clearTokens()
    clearRefreshTimer()
    setUser(null)
  }, [clearRefreshTimer])

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await loginRequest(email, password)
      setTokens(tokens)
      scheduleRefresh(tokens.access)
      const me = await apiFetch<User>('/auth/me/')
      setUser(me)
    },
    [scheduleRefresh],
  )

  useEffect(() => {
    setSessionExpiredHandler(() => logout())
    return () => setSessionExpiredHandler(null)
  }, [logout])

  useEffect(() => {
    async function restoreSession() {
      const access = getAccessToken()
      const refresh = getRefreshToken()

      if (!access && !refresh) {
        setIsLoading(false)
        return
      }

      try {
        if (access) scheduleRefresh(access)
        const me = await apiFetch<User>('/auth/me/')
        setUser(me)
      } catch {
        clearTokens()
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    restoreSession()
    return () => clearRefreshTimer()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
