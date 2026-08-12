import { describe, it, expect, vi, beforeEach } from "vitest"
import { render } from "@/test-utils"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthContext, createMockAuthUser } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

const navigateMock = vi.fn()

vi.mock("@/components/navigation/app-navigate", () => ({
  AppNavigate: ({ to, replace }: { to: string; replace?: boolean }) => {
    navigateMock(to, { replace })
    return null
  },
}))

describe("ProtectedRoute", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows loading spinner while isLoading", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ isLoading: true }))
    const { container } = render(<ProtectedRoute />)
    const spinner = container.querySelector("svg")
    expect(spinner).toBeInTheDocument()
    expect(spinner!.className).toBeTruthy()
  })

  it("redirects to /login with returnUrl when unauthenticated", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ isAuthenticated: false }))
    render(<ProtectedRoute />, { initialEntries: ["/dashboard/reports?tab=1"] })
    expect(navigateMock).toHaveBeenCalledWith(
      "/login?returnUrl=%2Fdashboard%2Freports%3Ftab%3D1",
      { replace: true }
    )
  })

  it("renders without redirect when authenticated with no restrictions", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ isAuthenticated: true, user: createMockAuthUser() })
    )
    render(<ProtectedRoute />)
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("redirects to /dashboard when the role is not in allowedRoles", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        isAuthenticated: true,
        user: createMockAuthUser({ role: "dispatcher" }),
      })
    )
    render(<ProtectedRoute allowedRoles={["admin"]} />)
    expect(navigateMock).toHaveBeenCalledWith("/dashboard", { replace: true })
  })

  it("renders without redirect when the role is in allowedRoles", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        isAuthenticated: true,
        user: createMockAuthUser({ role: "admin" }),
      })
    )
    render(<ProtectedRoute allowedRoles={["admin"]} />)
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("redirects to /dashboard when requireAdmin is set but user is not admin", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        isAuthenticated: true,
        isAdmin: false,
        user: createMockAuthUser({ role: "dispatcher" }),
      })
    )
    render(<ProtectedRoute requireAdmin />)
    expect(navigateMock).toHaveBeenCalledWith("/dashboard", { replace: true })
  })

  it("renders without redirect when requireAdmin is set and user is admin", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        isAuthenticated: true,
        isAdmin: true,
        user: createMockAuthUser({ role: "admin" }),
      })
    )
    render(<ProtectedRoute requireAdmin />)
    expect(navigateMock).not.toHaveBeenCalled()
  })
})
