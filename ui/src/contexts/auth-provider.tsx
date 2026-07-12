import React, { createContext, useContext, useState, useCallback, useEffect } from "react"
import { api, setTokens, clearTokens, getStoredUser, getStoredRefreshToken, type UserInfo } from "@/lib/api"

// ── Types ──────────────────────────────────────────────────────────────

interface User {
  id: string
  email: string
  name: string
  avatar?: string
  role?: string
  company_id?: number
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string, companyName: string) => Promise<void>
  logout: () => Promise<void>
}

// ── Context ────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextType | undefined>(undefined)

function storedUserToUser(stored: UserInfo | null): User | null {
  if (!stored) return null
  return {
    id: String(stored.id),
    email: stored.email,
    name: stored.display_name || stored.email.split("@")[0],
    role: stored.role,
    company_id: stored.company_id,
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => storedUserToUser(getStoredUser()))

  // Rehydrate from localStorage on mount
  useEffect(() => {
    const stored = getStoredUser()
    if (stored) {
      setUser(storedUserToUser(stored))
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.postForm<{
      access_token: string
      refresh_token: string
      token_type: string
      expires_in: number
    }>("/api/v1/auth/token", {
      username: email,
      password,
    })

    // After login, fetch user info from stored registration or decode token
    // Since login doesn't return user info, we construct minimal user from email
    const userInfo: UserInfo = {
      id: 0,
      email,
      role: "",
      company_id: 0,
      display_name: email.split("@")[0],
    }

    setTokens(tokens, userInfo)
    setUser({
      id: String(userInfo.id),
      email: userInfo.email,
      name: userInfo.display_name,
    })
  }, [])

  const register = useCallback(async (email: string, password: string, name: string, companyName: string) => {
    const data = await api.post<{
      access_token: string
      refresh_token: string
      token_type: string
      expires_in: number
      user: UserInfo
    }>("/api/v1/registration/register", {
      email,
      password,
      display_name: name,
      company_name: companyName,
    })

    setTokens(
      {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        token_type: data.token_type,
        expires_in: data.expires_in,
      },
      data.user,
    )

    setUser({
      id: String(data.user.id),
      email: data.user.email,
      name: data.user.display_name || name,
      role: data.user.role,
      company_id: data.user.company_id,
    })
  }, [])

  const logout = useCallback(async () => {
    try {
      // The refresh token is sent as an httpOnly cookie automatically.
      // Sending an empty body is fine — the server reads the cookie.
      await api.post("/api/v1/auth/logout", {})
    } catch {
      // Ignore logout errors — clear tokens anyway
    }
    clearTokens()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
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

// ── Hook ───────────────────────────────────────────────────────────────

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
