import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor, act } from "@testing-library/react"
import { useAuth, AuthProvider } from "@/contexts/auth-provider"
import { authApi } from "@/api/endpoints"
import { getAccessToken } from "@/api/client"
import { createMockAuthUser, mockAxiosResponse } from "@/test-utils"
import axios from "axios"

vi.mock("@/api/endpoints", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getMe: vi.fn(),
    refreshToken: vi.fn(),
    verifyMfa: vi.fn(),
  },
}))

// Mock axios.post used by refreshUser() in auth-provider
// The apiClient (used by authApi) is already mocked via @/api/endpoints
vi.mock("axios", () => {
  const mockAxiosInstance = {
    interceptors: {
      request: { use: vi.fn(), eject: vi.fn(), clear: vi.fn() },
      response: { use: vi.fn(), eject: vi.fn(), clear: vi.fn() },
    },
    defaults: {},
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  }
  return {
    default: {
      post: vi.fn(),
      create: vi.fn(() => mockAxiosInstance),
    },
  }
})

const mockUser = createMockAuthUser()

function renderAuthHook() {
  return renderHook(() => useAuth(), {
    wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
  })
}

function mockCookieRefresh(accessToken = "fresh-access-token") {
  vi.mocked(axios.post).mockResolvedValueOnce({
    data: { access_token: accessToken, token_type: "bearer" },
  } as any)
}

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
  })

  it("starts in loading state with no user when cookie refresh fails", async () => {
    vi.mocked(axios.post).mockRejectedValueOnce(new Error("No session cookie"))
    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(sessionStorage.getItem("operion-refresh-token")).toBeNull()
  })

  it("loads user from getMe when cookie refresh succeeds", async () => {
    // refreshUser posts to /auth/refresh with NO body — cookie sent automatically
    mockCookieRefresh("fresh-access-token")
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).not.toBeNull()
    expect(result.current.user?.email).toBe("test@operionerp.xyz")
    expect(result.current.user?.role).toBe("dispatcher")
    expect(result.current.isAuthenticated).toBe(true)
    expect(getAccessToken()).toBe("fresh-access-token")
    // Refresh token is NOT persisted anywhere
    expect(sessionStorage.getItem("operion-refresh-token")).toBeNull()
  })

  it("calls /auth/refresh with no body payload", async () => {
    mockCookieRefresh()
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

    renderAuthHook()
    await waitFor(() => expect(authApi.getMe).toHaveBeenCalled())

    const [url, body] = vi.mocked(axios.post).mock.calls[0]
    expect(url).toContain("/api/v1/auth/refresh")
    expect(body).toBeNull()
  })

  it("clears user when cookie refresh or getMe fails", async () => {
    vi.mocked(axios.post).mockRejectedValueOnce(new Error("Session expired"))

    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(getAccessToken()).toBeNull()
    expect(sessionStorage.getItem("operion-refresh-token")).toBeNull()
  })

  it("login keeps access token in memory and never persists a refresh token", async () => {
    const loginResponse = {
      access_token: "mock-access-token",
      token_type: "bearer",
      expires_in: 900,
    }
    vi.mocked(authApi.login).mockResolvedValueOnce({ data: loginResponse } as any)
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

    const { result } = renderAuthHook()
    await act(async () => {
      await result.current.login("test@c.com", "password")
    })

    expect(authApi.login).toHaveBeenCalledWith({ username: "test@c.com", password: "password" })
    expect(getAccessToken()).toBe("mock-access-token")
    expect(sessionStorage.getItem("operion-refresh-token")).toBeNull()
    expect(localStorage.getItem("operion-refresh-token")).toBeNull()
    expect(result.current.user?.email).toBe("test@operionerp.xyz")
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

  it("register keeps access token in memory and never persists a refresh token", async () => {
    const registerResponse = {
      access_token: "mock-access-token",
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
    expect(getAccessToken()).toBe("mock-access-token")
    expect(sessionStorage.getItem("operion-refresh-token")).toBeNull()
    expect(result.current.user).toEqual(mockUser)
  })

  it("logout calls server logout and clears tokens and user", async () => {
    mockCookieRefresh()
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isAuthenticated).toBe(true)

    act(() => {
      result.current.logout()
    })

    expect(authApi.logout).toHaveBeenCalled()
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(getAccessToken()).toBeNull()
    expect(sessionStorage.getItem("operion-refresh-token")).toBeNull()
  })

  it("logout still clears local state when the server logout call fails", async () => {
    mockCookieRefresh()
    vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))
    vi.mocked(authApi.logout).mockRejectedValueOnce(new Error("network down"))

    const { result } = renderAuthHook()
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    act(() => {
      result.current.logout()
    })

    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(getAccessToken()).toBeNull()
    // The rejected logout promise is swallowed — no unhandled rejection.
    expect(vi.mocked(authApi.logout)).toHaveBeenCalled()
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

  describe("avatar persistence", () => {
    it("updateUser with avatar_url stores to localStorage", async () => {
      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      const userWithAvatar = { ...mockUser, avatar_url: "data:image/png;base64,abc123" }

      act(() => {
        result.current.updateUser(userWithAvatar)
      })

      expect(localStorage.getItem("operion-avatar-url")).toBe("data:image/png;base64,abc123")
    })

    it("updateUser without avatar_url does not clear stored avatar", async () => {
      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      // Pre-set avatar in localStorage
      localStorage.setItem("operion-avatar-url", "data:image/png;base64,existing")

      const userWithoutAvatar = { ...mockUser, avatar_url: undefined }

      act(() => {
        result.current.updateUser(userWithoutAvatar)
      })

      // Stored avatar should remain unchanged
      expect(localStorage.getItem("operion-avatar-url")).toBe("data:image/png;base64,existing")
    })

    it("refreshUser merges stored avatar from localStorage on getMe restore", async () => {
      localStorage.setItem("operion-avatar-url", "data:image/png;base64,stored-avatar")
      mockCookieRefresh("fresh-token")
      vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: { ...mockUser, avatar_url: undefined } }))

      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(result.current.user?.avatar_url).toBe("data:image/png;base64,stored-avatar")
    })

    it("login preserves stored avatar from localStorage", async () => {
      localStorage.setItem("operion-avatar-url", "data:image/png;base64,login-avatar")
      // Mount-time cookie refresh must succeed so it does not clear the stored avatar
      mockCookieRefresh()
      vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: { ...mockUser, avatar_url: undefined } }))
      vi.mocked(authApi.login).mockResolvedValueOnce({ data: { access_token: "mock-token", token_type: "bearer" } } as any)
      vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: { ...mockUser, avatar_url: undefined } }))

      const { result } = renderAuthHook()
      await act(async () => {
        await result.current.login("test@c.com", "password")
      })

      expect(result.current.user?.avatar_url).toBe("data:image/png;base64,login-avatar")
    })

    it("logout clears stored avatar", async () => {
      localStorage.setItem("operion-avatar-url", "data:image/png;base64,will-be-cleared")
      mockCookieRefresh()
      vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => {
        result.current.logout()
      })

      expect(localStorage.getItem("operion-avatar-url")).toBeNull()
    })
  })

  it("useAuth throws outside AuthProvider", () => {
    expect(() => {
      renderHook(() => useAuth())
    }).toThrow("useAuth must be used within AuthProvider")
  })

  describe("login turnstile token", () => {
    it("login forwards the turnstile token to the API", async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({ data: { access_token: "tok", token_type: "bearer" } } as any)
      vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

      const { result } = renderAuthHook()
      await act(async () => {
        await result.current.login("test@c.com", "password", true, "turnstile-abc")
      })

      expect(authApi.login).toHaveBeenCalledWith({
        username: "test@c.com",
        password: "password",
        turnstile_token: "turnstile-abc",
      })
      expect(result.current.isAuthenticated).toBe(true)
    })

    it("login without a turnstile token only sends username and password", async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({ data: { access_token: "tok", token_type: "bearer" } } as any)
      vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

      const { result } = renderAuthHook()
      await act(async () => {
        await result.current.login("test@c.com", "password")
      })

      expect(authApi.login).toHaveBeenCalledWith({ username: "test@c.com", password: "password" })
      expect(vi.mocked(authApi.login).mock.calls[0][0]).not.toHaveProperty("turnstile_token")
    })
  })

  describe("MFA login flow", () => {
    it("login with mfa_required defers authentication and stores the session token", async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        data: { mfa_required: true, mfa_session_token: "mfa-session-1", token_type: "bearer" },
      } as any)

      const { result } = renderAuthHook()
      let loginResult: { mfaRequired: boolean } | undefined
      await act(async () => {
        loginResult = await result.current.login("test@c.com", "password")
      })

      expect(loginResult).toEqual({ mfaRequired: true })
      expect(result.current.mfaRequired).toBe(true)
      expect(result.current.mfaSessionToken).toBe("mfa-session-1")
      expect(result.current.isAuthenticated).toBe(false)
      expect(getAccessToken()).toBeNull()
      // Profile is NOT fetched until MFA is verified
      expect(authApi.getMe).not.toHaveBeenCalled()
    })

    it("login with mfa_required but no session token leaves mfaSessionToken null", async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({ data: { mfa_required: true, token_type: "bearer" } } as any)

      const { result } = renderAuthHook()
      await act(async () => {
        await result.current.login("test@c.com", "password")
      })

      expect(result.current.mfaRequired).toBe(true)
      expect(result.current.mfaSessionToken).toBeNull()
    })
  })

  describe("verifyMfa", () => {
    it("throws when no MFA session token is available", async () => {
      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      await expect(
        act(async () => {
          await result.current.verifyMfa("123456")
        })
      ).rejects.toThrow("No MFA session token available")
      expect(authApi.verifyMfa).not.toHaveBeenCalled()
    })

    it("verifies the code, stores the access token and loads the user", async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        data: { mfa_required: true, mfa_session_token: "mfa-session-1", token_type: "bearer" },
      } as any)
      vi.mocked(authApi.verifyMfa).mockResolvedValueOnce({ access_token: "mfa-access-token", token_type: "bearer" } as any)
      vi.mocked(authApi.getMe).mockResolvedValueOnce(
        mockAxiosResponse({ user: { ...mockUser, avatar_url: "https://cdn.operion.dev/avatar.png" } })
      )

      const { result } = renderAuthHook()
      await act(async () => {
        await result.current.login("test@c.com", "password")
      })
      expect(result.current.mfaRequired).toBe(true)

      await act(async () => {
        await result.current.verifyMfa("123456")
      })

      expect(authApi.verifyMfa).toHaveBeenCalledWith("mfa-session-1", "123456")
      expect(getAccessToken()).toBe("mfa-access-token")
      expect(result.current.mfaRequired).toBe(false)
      expect(result.current.mfaSessionToken).toBeNull()
      expect(result.current.user?.email).toBe("test@operionerp.xyz")
      expect(result.current.user?.avatar_url).toBe("https://cdn.operion.dev/avatar.png")
      expect(result.current.isAuthenticated).toBe(true)
    })

    it("falls back to the stored avatar when getMe returns no avatar_url", async () => {
      localStorage.setItem("operion-avatar-url", "data:image/png;base64,mfa-avatar")
      // Mount-time cookie refresh must succeed so it does not clear the stored avatar.
      mockCookieRefresh()
      vi.mocked(authApi.getMe).mockResolvedValue(mockAxiosResponse({ user: { ...mockUser, avatar_url: undefined } }))
      vi.mocked(authApi.login).mockResolvedValueOnce({
        data: { mfa_required: true, mfa_session_token: "mfa-session-1", token_type: "bearer" },
      } as any)
      vi.mocked(authApi.verifyMfa).mockResolvedValueOnce({ access_token: "mfa-access-token", token_type: "bearer" } as any)

      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))
      await act(async () => {
        await result.current.login("test@c.com", "password")
      })
      await act(async () => {
        await result.current.verifyMfa("123456")
      })

      expect(result.current.user?.avatar_url).toBe("data:image/png;base64,mfa-avatar")
    })

    it("leaves avatar_url undefined when neither getMe nor storage provides one", async () => {
      mockCookieRefresh()
      vi.mocked(authApi.getMe).mockResolvedValue(mockAxiosResponse({ user: { ...mockUser, avatar_url: undefined } }))
      vi.mocked(authApi.login).mockResolvedValueOnce({
        data: { mfa_required: true, mfa_session_token: "mfa-session-1", token_type: "bearer" },
      } as any)
      vi.mocked(authApi.verifyMfa).mockResolvedValueOnce({ access_token: "mfa-access-token", token_type: "bearer" } as any)

      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))
      await act(async () => {
        await result.current.login("test@c.com", "password")
      })
      await act(async () => {
        await result.current.verifyMfa("123456")
      })

      expect(result.current.user?.avatar_url).toBeUndefined()
    })
  })

  describe("register without user payload", () => {
    it("still stores the access token but leaves the user null", async () => {
      vi.mocked(authApi.register).mockResolvedValueOnce({ data: { access_token: "reg-token", token_type: "bearer" } } as any)

      const { result } = renderAuthHook()
      await act(async () => {
        await result.current.register({ email: "new@c.com", password: "password123", name: "New User" })
      })

      expect(getAccessToken()).toBe("reg-token")
      expect(result.current.user).toBeNull()
      expect(result.current.isAuthenticated).toBe(false)
    })
  })

  describe("permissions", () => {
    it("derives permissions and hasPermission from the loaded user role", async () => {
      mockCookieRefresh()
      vi.mocked(authApi.getMe).mockResolvedValueOnce(mockAxiosResponse({ user: mockUser }))

      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(result.current.permissions).toContain("support.tickets")
      expect(result.current.hasPermission("support.tickets")).toBe(true)
      expect(result.current.hasPermission("billing.manage")).toBe(false)
    })

    it("returns empty permissions and false hasPermission when logged out", async () => {
      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(result.current.permissions).toEqual([])
      expect(result.current.hasPermission("support.tickets")).toBe(false)
    })
  })

  describe("localStorage failure tolerance", () => {
    it("refreshUser tolerates a throwing localStorage read when restoring the avatar", async () => {
      vi.spyOn(localStorage, "getItem").mockImplementationOnce(() => {
        throw new Error("storage blocked")
      })
      mockCookieRefresh()
      vi.mocked(authApi.getMe).mockResolvedValueOnce(
        mockAxiosResponse({ user: { ...mockUser, avatar_url: "https://cdn.operion.dev/avatar.png" } })
      )

      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(result.current.user?.email).toBe("test@operionerp.xyz")
      expect(result.current.user?.avatar_url).toBe("https://cdn.operion.dev/avatar.png")
    })

    it("updateUser tolerates a throwing localStorage write", async () => {
      vi.spyOn(localStorage, "setItem").mockImplementationOnce(() => {
        throw new Error("quota exceeded")
      })

      const { result } = renderAuthHook()
      await waitFor(() => expect(result.current.isLoading).toBe(false))

      const userWithAvatar = { ...mockUser, avatar_url: "data:image/png;base64,abc" }
      act(() => {
        result.current.updateUser(userWithAvatar)
      })

      // State update still succeeds even though persistence failed
      expect(result.current.user).toEqual(userWithAvatar)
    })
  })
})
