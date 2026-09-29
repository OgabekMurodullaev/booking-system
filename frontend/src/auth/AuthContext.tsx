import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { apiClient, refreshAccessToken } from '@/api/client'
import { unwrap } from '@/api/errors'
import type { components } from '@/api/schema'
import {
  clearTokens,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from '@/api/tokens'

export type User = components['schemas']['User']

interface AuthContextValue {
  user: User | null
  /** True only during the boot-time silent refresh; never true again after that. */
  isLoading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      if (!getRefreshToken()) {
        setIsLoading(false)
        return
      }
      try {
        await refreshAccessToken()
        const me = await unwrap(apiClient.GET('/api/v1/auth/me/'))
        if (!cancelled) setUser(me)
      } catch {
        clearTokens()
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  async function login(email: string, password: string): Promise<User> {
    const data = await unwrap(
      apiClient.POST('/api/v1/auth/login/', { body: { email, password } }),
    )
    setAccessToken(data.access)
    setRefreshToken(data.refresh)
    setUser(data.user)
    return data.user
  }

  async function logout(): Promise<void> {
    const refresh = getRefreshToken()
    if (refresh) {
      try {
        await apiClient.POST('/api/v1/auth/logout/', { body: { refresh } })
      } catch {
        // Best-effort: clear local state regardless of whether the server call
        // itself succeeded (an already-expired refresh token shouldn't block logout).
      }
    }
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
