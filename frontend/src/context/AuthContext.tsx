import { createContext, useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import apiClient from '../api/client'
import { decodeToken, getStoredToken, isTokenExpired } from '../utils/auth'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setUser(null)
  }, [])

  useEffect(() => {
    const token = getStoredToken()
    if (!token) {
      setLoading(false)
      return
    }
    try {
      const payload = decodeToken(token)
      if (isTokenExpired(payload)) {
        localStorage.removeItem('token')
        setLoading(false)
        return
      }
    } catch {
      localStorage.removeItem('token')
      setLoading(false)
      return
    }

    apiClient
      .get<User>('/api/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.removeItem('token')
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post<{ access_token: string; token_type: string }>(
      '/api/auth/login',
      { email, password },
    )
    localStorage.setItem('token', data.access_token)
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
