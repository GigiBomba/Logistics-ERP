import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react"
import axios from "axios"
import type { AuthResponse, LoginRequest, User } from "@/types"
import { authApi } from "@/api/endpoints"
import { getAllPermissions, hasPermission as checkPermission, type Permission } from "@/lib/permissions"
import { setAccessToken } from "@/api/client"
import { apiConfig } from "@/config/site"

const AVATAR_STORAGE_KEY = "operion-avatar-url"

function getStoredAvatarUrl(): string | null {
  try {
    return localStorage.getItem(AVATAR_STORAGE_KEY)
  } catch {
    return null
  }
}

function storeAvatarUrl(url: string): void {
  try {
    localStorage.setItem(AVATAR_STORAGE_KEY, url)
  } catch {
    // localStorage quota exceeded or unavailable — silently ignore
  }
}

function clearStoredAvatar(): void {
  try {
    localStorage.removeItem(AVATAR_STORAGE_KEY)
  } catch {
    // ignore
  }
}

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  isAdmin: boolean
  permissions: Permission[]
  hasPermission: (permission: Permission) => boolean
  mfaRequired: boolean
  mfaSessionToken: string | null
  login: (email: string, password: string, rememberMe?: boolean, turnstileToken?: string) => Promise<{ mfaRequired: boolean }>
  register: (data: { email: string; password: string; name: string; company_name?: string; turnstile_token?: string }) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  updateUser: (user: User) => void
  verifyMfa: (code: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [mfaRequired, setMfaRequired] = useState(false)
  const [mfaSessionToken, setMfaSessionToken] = useState<string | null>(null)
  const mfaSessionTokenRef = useRef<string | null>(null)

  const refreshUser = useCallback(async () => {
    try {
      // Exchange the httpOnly refresh cookie for a fresh access token.
      // No body — the backend reads the refresh token from the cookie.
      const { data } = await axios.post<Pick<AuthResponse, "access_token">>(
        `${apiConfig.baseUrl}/api/v1/auth/refresh`,
        null,
        { withCredentials: true }
      )
      setAccessToken(data.access_token)

      // Clean up legacy localStorage tokens
      localStorage.removeItem("operion-access-token")
      localStorage.removeItem("operion-refresh-token")

      // Fetch full user profile from authoritative /me endpoint
      const { data: meData } = await authApi.getMe()
      const storedAvatar = getStoredAvatarUrl()
      setUser({
        ...meData.user,
        avatar_url: meData.user.avatar_url ?? storedAvatar ?? undefined,
      })
    } catch {
      // No session cookie / token invalid / network failure — clear auth state
      setAccessToken(null)
      localStorage.removeItem("operion-access-token")
      localStorage.removeItem("operion-refresh-token")
      sessionStorage.removeItem("operion-refresh-token")
      clearStoredAvatar()
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const login = useCallback(async (email: string, password: string, _rememberMe?: boolean, turnstileToken?: string) => {
    const credentials: LoginRequest = { username: email, password }
    if (turnstileToken) {
      credentials.turnstile_token = turnstileToken
    }
    const { data } = await authApi.login(credentials)

    // If MFA is required, store the session token and defer authentication
    if (data.mfa_required) {
      setMfaSessionToken(data.mfa_session_token ?? null)
      mfaSessionTokenRef.current = data.mfa_session_token ?? null
      setMfaRequired(true)
      return { mfaRequired: true }
    }

    // Access token lives in memory; the refresh token is an httpOnly cookie
    // set by the backend (never persisted to storage).
    setAccessToken(data.access_token)

    // Clean up legacy localStorage tokens
    localStorage.removeItem("operion-access-token")
    localStorage.removeItem("operion-refresh-token")

    // Fetch full user profile from authoritative /me endpoint
    const { data: meData } = await authApi.getMe()
    const storedAvatar = getStoredAvatarUrl()
    setUser({
      ...meData.user,
      avatar_url: meData.user.avatar_url ?? storedAvatar ?? undefined,
    })

    return { mfaRequired: false }
  }, [])

  const register = useCallback(async (registerData: { email: string; password: string; name: string; company_name?: string; turnstile_token?: string }) => {
    const { data } = await authApi.register(registerData)
    // Registration response includes user
    setAccessToken(data.access_token)

    // Clean up legacy localStorage tokens
    localStorage.removeItem("operion-access-token")
    localStorage.removeItem("operion-refresh-token")

    if (data.user) {
      setUser(data.user as User)
    }
  }, [])

  const logout = useCallback(() => {
    // Best-effort server logout so the backend clears the httpOnly refresh cookie.
    Promise.resolve(authApi.logout()).catch(() => {})
    setAccessToken(null)
    // Clean up legacy localStorage tokens (backward compat)
    localStorage.removeItem("operion-access-token")
    localStorage.removeItem("operion-refresh-token")
    sessionStorage.removeItem("operion-refresh-token")
    clearStoredAvatar()
    setUser(null)
    setMfaRequired(false)
    setMfaSessionToken(null)
    mfaSessionTokenRef.current = null
  }, [])

  const verifyMfa = useCallback(async (code: string) => {
    const token = mfaSessionTokenRef.current
    if (!token) throw new Error("No MFA session token available")

    const response = await authApi.verifyMfa(token, code)

    // After MFA verify the access token comes back in the body; the refresh
    // token is delivered as an httpOnly cookie (no body value to persist).
    setAccessToken(response.access_token)

    // Clean up legacy localStorage tokens
    localStorage.removeItem("operion-access-token")
    localStorage.removeItem("operion-refresh-token")

    // Fetch full user profile from authoritative /me endpoint
    const { data: meData } = await authApi.getMe()
    const storedAvatar = getStoredAvatarUrl()
    setUser({
      ...meData.user,
      avatar_url: meData.user.avatar_url ?? storedAvatar ?? undefined,
    })

    // Clear MFA state
    setMfaRequired(false)
    setMfaSessionToken(null)
    mfaSessionTokenRef.current = null
  }, [])

  const updateUser = useCallback((updated: User) => {
    if (updated.avatar_url) {
      storeAvatarUrl(updated.avatar_url)
    }
    setUser(updated)
  }, [])

  const isAdmin = user?.is_admin === true || user?.role === "admin"
  const permissions = user ? getAllPermissions(user.role) : []
  const hasPermission = useCallback(
    (permission: Permission) => (user ? checkPermission(user.role, permission) : false),
    [user],
  )

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isAdmin,
        permissions,
        hasPermission,
        mfaRequired,
        mfaSessionToken,
        login,
        register,
        logout,
        refreshUser,
        updateUser,
        verifyMfa,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
