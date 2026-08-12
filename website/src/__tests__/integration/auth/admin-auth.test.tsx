import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, render, screen } from "@testing-library/react"
import { MemoryRouter, Routes, Route } from "react-router"
import { useAuth } from "@/contexts/auth-provider"
import { ProtectedRoute, AdminRoute } from "@/components/auth/protected-route"
import { createMockAuthUser, createMockAuthContext } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

// FU-A: guard components now delegate redirects to vike via AppNavigate instead
// of react-router's render-time <Navigate>. Assert the requested redirect target.
vi.mock("@/components/navigation/app-navigate", () => ({
  AppNavigate: ({ to, replace }: { to: string; replace?: boolean }) => (
    <div data-testid="app-navigate" data-to={to} data-replace={String(replace)} />
  ),
}))

describe("AuthContext - isAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("exposes isAdmin as false when user.role is 'dispatcher'", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        user: createMockAuthUser({ role: "dispatcher", is_admin: false }),
        isAuthenticated: true,
        isAdmin: false,
      })
    )

    const { result } = renderHook(() => useAuth())

    expect(result.current.isAdmin).toBe(false)
    expect(result.current.user?.role).toBe("dispatcher")
    expect(result.current.user?.is_admin).toBe(false)
  })

  it("exposes isAdmin as true when user.role is 'admin'", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        user: createMockAuthUser({ role: "admin", is_admin: true }),
        isAuthenticated: true,
        isAdmin: true,
      })
    )

    const { result } = renderHook(() => useAuth())

    expect(result.current.isAdmin).toBe(true)
    expect(result.current.user?.role).toBe("admin")
    expect(result.current.user?.is_admin).toBe(true)
  })

  it("exposes isAdmin as false when user has no admin privileges", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        user: createMockAuthUser({ role: "manager", is_admin: false }),
        isAuthenticated: true,
        isAdmin: false,
      })
    )

    const { result } = renderHook(() => useAuth())

    expect(result.current.isAdmin).toBe(false)
    expect(result.current.user?.role).toBe("manager")
  })

  it("exposes isAdmin as true when is_admin flag is true even if role is not admin", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        user: createMockAuthUser({ role: "dispatcher", is_admin: true }),
        isAuthenticated: true,
        isAdmin: true,
      })
    )

    const { result } = renderHook(() => useAuth())

    expect(result.current.isAdmin).toBe(true)
    expect(result.current.user?.role).toBe("dispatcher")
    expect(result.current.user?.is_admin).toBe(true)
  })
})

describe("ProtectedRoute and AdminRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function renderRoute(isAdmin: boolean, requireAdmin = false) {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({
        isAuthenticated: true,
        isAdmin,
        isLoading: false,
        user: createMockAuthUser({ role: isAdmin ? "admin" : "dispatcher", is_admin: isAdmin }),
      })
    )

    return render(
      <MemoryRouter initialEntries={["/protected"]}>
        <Routes>
          <Route
            element={
              requireAdmin ? <AdminRoute /> : <ProtectedRoute requireAdmin={requireAdmin} />
            }
          >
            <Route
              path="/protected"
              element={<div data-testid="protected-content">Protected Content</div>}
            />
          </Route>
          <Route
            path="/dashboard"
            element={<div data-testid="dashboard-redirect">Dashboard</div>}
          />
          <Route
            path="/login"
            element={<div data-testid="login-redirect">Login</div>}
          />
        </Routes>
      </MemoryRouter>
    )
  }

  it("AdminRoute redirects non-admin users to /dashboard", () => {
    renderRoute(false, true)

    expect(screen.getByTestId("app-navigate")).toHaveAttribute("data-to", "/dashboard")
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument()
  })

  it("AdminRoute allows admin users to access children", () => {
    renderRoute(true, true)

    expect(screen.getByTestId("protected-content")).toBeInTheDocument()
    expect(screen.queryByTestId("dashboard-redirect")).not.toBeInTheDocument()
  })

  it("ProtectedRoute with requireAdmin={false} allows regular users", () => {
    renderRoute(false, false)

    expect(screen.getByTestId("protected-content")).toBeInTheDocument()
    expect(screen.queryByTestId("dashboard-redirect")).not.toBeInTheDocument()
  })
})
