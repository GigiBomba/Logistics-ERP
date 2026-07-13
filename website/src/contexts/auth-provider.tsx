import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react"
import type { User } from "@/types"
import { authApi } from "@/api/endpoints"
import { verifyJwt } from "@/services/jwt"

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  isAdmin: boolean
  login: (email: string, password: string) => Promise<void>
  register: (data: { email: string; password: string; name: string; company_name?: string }) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  updateUser: (user: User) => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    const token = localStorage.getItem("operion-access-token")
    if (!token) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      // TODO: Implement when backend endpoint is ready
      // const { data } = await authApi.getMe()
      // setUser(data as User)

      // If /me fails, attempt to verify and decode from JWT claims for a minimal user
      const claims = await verifyJwt(token)
      if (claims) {
        setUser({
          id: (claims.sub as string) || 0,
          email: (claims.sub as string) || "",
          role: (claims.role as User["role"]) || "dispatcher",
          is_admin: claims.is_admin === true || claims.role === "admin",
          company_id: (claims.company_id as number) ?? null,
        })
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await authApi.login({ username: email, password })
    localStorage.setItem("operion-access-token", data.access_token)
    localStorage.setItem("operion-refresh-token", data.refresh_token)

    // Backend does not return user on login; verify and decode from JWT claims
    // NOTE: Backend JWT contains email in 'sub', not user ID.
    //       DB user ID requires a /me endpoint or backend JWT change.
    const claims = verifyJwt(data.access_token)
    if (!claims) throw new Error("Invalid token")
    setUser({
      id: (claims.sub as string) || 0,
      email: (claims.sub as string) || email,
      role: (claims.role as User["role"]) || "dispatcher",
      is_admin: claims.is_admin === true || claims.role === "admin",
      company_id: (claims.company_id as number) ?? null,
    })
  }, [])

  const register = useCallback(async (registerData: { email: string; password: string; name: string; company_name?: string }) => {
    const { data } = await authApi.register(registerData)
    // Registration response includes user
    localStorage.setItem("operion-access-token", data.access_token)
    localStorage.setItem("operion-refresh-token", data.refresh_token)
    if (data.user) {
      setUser(data.user as User)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem("operion-access-token")
    localStorage.removeItem("operion-refresh-token")
    setUser(null)
  }, [])

  const updateUser = useCallback((updated: User) => {
    setUser(updated)
  }, [])

  const isAdmin = user?.is_admin === true || user?.role === "admin"

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isAdmin,
        login,
        register,
        logout,
        refreshUser,
        updateUser,
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
