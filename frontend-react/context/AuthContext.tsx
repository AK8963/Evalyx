'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import { api } from '@/lib/api'
import type { User } from '@/types'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string) => Promise<void>
  register: (email: string, name: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const applyToken = useCallback(async (t: string) => {
    localStorage.setItem('trustbrain_token', t)
    setToken(t)
    try {
      const me = await api.auth.me()
      setUser(me)
    } catch {
      localStorage.removeItem('trustbrain_token')
      setToken(null)
      setUser(null)
    }
  }, [])

  // Restore session on mount
  useEffect(() => {
    const stored = localStorage.getItem('trustbrain_token')
    if (stored) {
      applyToken(stored).finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [applyToken])

  const login = useCallback(
    async (email: string) => {
      const res = await api.auth.login(email)
      await applyToken(res.access_token)
    },
    [applyToken],
  )

  const register = useCallback(
    async (email: string, name: string) => {
      const res = await api.auth.register(email, name)
      await applyToken(res.access_token)
    },
    [applyToken],
  )

  const logout = useCallback(() => {
    localStorage.removeItem('traciq_token')
    setToken(null)
    setUser(null)
    window.location.href = '/login'
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
