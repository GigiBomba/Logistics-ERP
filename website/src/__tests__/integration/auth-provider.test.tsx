import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor, act } from "@testing-library/react"
import { useAuth, AuthProvider } from "@/contexts/auth-provider"
import { authApi } from "@/api/endpoints"
import { verifyJwt } from "@/services/jwt"
import { createMockAuthUser } from "@/test-utils"

vi.mock("@/api/endpoints", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getMe: vi.fn(),
  },
}))

vi.mock("@/services/jwt", () => ({
  verifyJwt: vi.fn(),
}))

// Helper: create a mock JWT with base64-encoded claims
function createMockJwt(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }))
  const payload = btoa(JSON.stringify(claims))
  const signature = btoa("mock-signature")
  return `${header}.${payload}.${signature}`
}

const mockUser = createMockAuthUser()

function renderAuthHook() {
  return renderHook(() => useAuth(), {
    wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
  })
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    // Mock verifyJwt to parse the JWT and return claims
    vi.mocked(verifyJwt).mockImplementation(async (token: string) => {
      try {
        const payload = token.split(".")[1]
        return JSON.parse(atob(payload)) as any
      } catch {
        return null
      }
    })
  })

  it("starts in loading state with no user when no token", async () => {
    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })

  it("fetches user when token exists and getMe succeeds", async () => {
    localStorage.setItem("operion-access-token", "valid-token")
    vi.mocked(authApi.getMe).mockResolvedValueOnce({ data: mockUser } as any)

    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(authApi.getMe).toHaveBeenCalled()
    expect(result.current.user).toEqual(mockUser)
    expect(result.current.isAuthenticated).toBe(true)
  })

  it("falls back to JWT decode when getMe fails", async () => {
    const token = createMockJwt({ sub: "test@operion.com", role: "dispatcher", company_id: 1 })
    localStorage.setItem("operion-access-token", token)
    vi.mocked(authApi.getMe).mockRejectedValueOnce(new Error("Unauthorized"))

    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).not.toBeNull()
    expect(result.current.user?.email).toBe("test@operion.com")
    expect(result.current.user?.role).toBe("dispatcher")
    expect(result.current.isAuthenticated).toBe(true)
  })

  it("login stores tokens and sets user from JWT claims", async () => {
    const accessToken = createMockJwt({ sub: "test@c.com", role: "dispatcher" })
    const loginResponse = {
      access_token: accessToken,
      refresh_token: "new-refresh-token",
      token_type: "bearer",
      expires_in: 900,
    }
    vi.mocked(authApi.login).mockResolvedValueOnce({ data: loginResponse } as any)

    const { result } = renderAuthHook()
    await act(async () => {
      await result.current.login("test@c.com", "password")
    })

    expect(authApi.login).toHaveBeenCalledWith({ username: "test@c.com", password: "password" })
    expect(localStorage.getItem("operion-access-token")).toBe(accessToken)
    expect(localStorage.getItem("operion-refresh-token")).toBe("new-refresh-token")
    expect(result.current.user?.email).toBe("test@c.com")
    expect(result.current.user?.role).toBe("dispatcher")
    expect(result.current.isAuthenticated).toBe(true)
  })

  it("login propagates errors", async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce(new Error("Invalid credentials"))

    const { result } = renderAuthHook()
    await expect(
      act(async () => {
        await result.current.login("bad@c.com", "wrong")
      })
    ).rejects.toThrow("Invalid credentials")
    expect(result.current.isAuthenticated).toBe(false)
  })

  it("register stores tokens and sets user from response", async () => {
    const accessToken = createMockJwt({ sub: "new@c.com", role: "dispatcher" })
    const registerResponse = {
      access_token: accessToken,
      refresh_token: "new-refresh-token",
      token_type: "bearer",
      user: mockUser,
    }
    vi.mocked(authApi.register).mockResolvedValueOnce({ data: registerResponse } as any)
    const registerData = { email: "new@c.com", password: "password123", name: "New User" }

    const { result } = renderAuthHook()
    await act(async () => {
      await result.current.register(registerData)
    })

    expect(authApi.register).toHaveBeenCalledWith(registerData)
    expect(localStorage.getItem("operion-access-token")).toBe(accessToken)
    expect(result.current.user).toEqual(mockUser)
  })

  it("logout clears tokens and user", async () => {
    const token = createMockJwt({ sub: "test@c.com", role: "dispatcher" })
    localStorage.setItem("operion-access-token", token)
    localStorage.setItem("operion-refresh-token", "rtoken")
    vi.mocked(authApi.getMe).mockResolvedValueOnce({ data: mockUser } as any)

    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isAuthenticated).toBe(true)

    act(() => {
      result.current.logout()
    })

    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(localStorage.getItem("operion-access-token")).toBeNull()
    expect(localStorage.getItem("operion-refresh-token")).toBeNull()
  })

  it("updateUser updates the user state", async () => {
    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    act(() => {
      result.current.updateUser(mockUser)
    })

    expect(result.current.user).toEqual(mockUser)
    expect(result.current.isAuthenticated).toBe(true)
  })

  it("useAuth throws outside AuthProvider", () => {
    expect(() => {
      renderHook(() => useAuth())
    }).toThrow("useAuth must be used within AuthProvider")
  })
})
