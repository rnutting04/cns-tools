import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import apiClient, { setAccessToken } from '../api/client'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    setAccessToken(null)
    setUser(null)
    // Best-effort server call to revoke the refresh token cookie.
    apiClient.post('/api/auth/logout').catch(() => {})
  }, [])

  useEffect(() => {
    // On mount, attempt to restore the session from the httpOnly refresh token
    // cookie. If no cookie exists (or it's expired/revoked) the server returns
    // 401 and we land at loading=false with user=null.
    apiClient
      .post<{ access_token: string }>('/api/auth/refresh')
      .then((res) => {
        setAccessToken(res.data.access_token)
        return apiClient.get<User>('/api/auth/me')
      })
      .then((res) => setUser(res.data))
      .catch(() => {
        setAccessToken(null)
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post<{ access_token: string; token_type: string }>(
      '/api/auth/login',
      { email, password },
    )
    setAccessToken(data.access_token)
    const me = await apiClient.get<User>('/api/auth/me')
    setUser(me.data)
  }, [])

  const refreshUser = useCallback(async () => {
    const me = await apiClient.get<User>('/api/auth/me')
    setUser(me.data)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
