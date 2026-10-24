import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

export type AuthUser = {
  id: string
  email: string
  full_name: string
  role: string
  institution_id: string | null
  permissions: string[]
}

type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  apiFetch: (path: string, init?: RequestInit) => Promise<Response>
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const AuthContext = createContext<AuthContextValue | null>(null)

async function readUser(token: string): Promise<AuthUser> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'include',
  })
  if (!response.ok) throw new Error('Session could not be restored')
  return response.json() as Promise<AuthUser>
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const accessToken = useRef<string | null>(null)
  const sessionEpoch = useRef(0)

  const clearSession = useCallback(() => {
    accessToken.current = null
    setUser(null)
  }, [])

  const refreshSession = useCallback(async () => {
    const epoch = sessionEpoch.current
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) throw new Error('Refresh failed')
      const body = (await response.json()) as { access_token: string }
      if (epoch !== sessionEpoch.current) return false
      const profile = await readUser(body.access_token)
      if (epoch !== sessionEpoch.current) return false
      accessToken.current = body.access_token
      setUser(profile)
      return true
    } catch {
      if (epoch === sessionEpoch.current) clearSession()
      return false
    }
  }, [clearSession])

  useEffect(() => {
    let mounted = true
    void refreshSession().finally(() => {
      if (mounted) setLoading(false)
    })
    return () => {
      mounted = false
    }
  }, [refreshSession])

  const login = useCallback(async (email: string, password: string) => {
    const epoch = ++sessionEpoch.current
    const response = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) throw new Error('Email or password is incorrect.')
    const body = (await response.json()) as { access_token: string }
    try {
      const profile = await readUser(body.access_token)
      if (epoch !== sessionEpoch.current) return
      accessToken.current = body.access_token
      setUser(profile)
    } catch {
      if (epoch === sessionEpoch.current) clearSession()
      throw new Error('Your session could not be started. Please try again.')
    }
  }, [clearSession])

  const logout = useCallback(async () => {
    sessionEpoch.current += 1
    try {
      await fetch(`${apiBaseUrl}/api/v1/auth/logout`, { method: 'POST', credentials: 'include' })
    } finally {
      clearSession()
    }
  }, [clearSession])

  const apiFetch = useCallback(async (path: string, init: RequestInit = {}) => {
    const url = path.startsWith('http') ? path : `${apiBaseUrl}${path}`
    const perform = (token: string | null) => {
      const headers = new Headers(init.headers)
      if (token) headers.set('Authorization', `Bearer ${token}`)
      return fetch(url, { ...init, headers, credentials: 'include' })
    }
    const first = await perform(accessToken.current)
    if (first.status !== 401 || /\/auth\/(login|refresh|logout)(\?|$)/.test(url)) return first
    if (!(await refreshSession())) return first
    return perform(accessToken.current)
  }, [refreshSession])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, apiFetch }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
