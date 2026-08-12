import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { Routes, Route } from "react-router"
import MaintenanceGuard from "@/components/shared/maintenance-guard"

const mockEnv = vi.hoisted(() => ({
  envConfig: {
    turnstileSiteKey: "",
    maintenanceMode: false,
    stripePublishableKey: "",
  },
}))

vi.mock("@/config/env", () => ({
  envConfig: mockEnv.envConfig,
}))

// FU-A: the guard now delegates redirects to vike via AppNavigate instead of
// react-router's render-time <Navigate>. Assert the requested redirect target.
vi.mock("@/components/navigation/app-navigate", () => ({
  AppNavigate: ({ to, replace }: { to: string; replace?: boolean }) => (
    <div data-testid="app-navigate" data-to={to} data-replace={String(replace)} />
  ),
}))

function GuardedRoutes() {
  return (
    <Routes>
      <Route element={<MaintenanceGuard />}>
        <Route path="/public-page" element={<div>Public Content</div>} />
        <Route path="/dashboard/things" element={<div>Dashboard Content</div>} />
        <Route path="/login" element={<div>Login Content</div>} />
        <Route path="/auth/mfa-challenge" element={<div>Auth MFA Content</div>} />
        <Route path="/500" element={<div>Error Page</div>} />
        <Route path="/offline" element={<div>Offline Page</div>} />
        <Route path="/maintenance" element={<div>Maintenance Page</div>} />
      </Route>
    </Routes>
  )
}

describe("MaintenanceGuard", () => {
  beforeEach(() => {
    mockEnv.envConfig.maintenanceMode = false
  })

  it("renders children when maintenance mode is off", () => {
    render(<GuardedRoutes />, { initialEntries: ["/public-page"] })
    expect(screen.getByText("Public Content")).toBeInTheDocument()
  })

  it("redirects public routes to /maintenance when maintenance mode is on", () => {
    mockEnv.envConfig.maintenanceMode = true
    render(<GuardedRoutes />, { initialEntries: ["/public-page"] })
    expect(screen.getByTestId("app-navigate")).toHaveAttribute("data-to", "/maintenance")
    expect(screen.queryByText("Public Content")).not.toBeInTheDocument()
  })

  it("keeps dashboard routes accessible during maintenance", () => {
    mockEnv.envConfig.maintenanceMode = true
    render(<GuardedRoutes />, { initialEntries: ["/dashboard/things"] })
    expect(screen.getByText("Dashboard Content")).toBeInTheDocument()
  })

  it("keeps auth routes accessible during maintenance", () => {
    mockEnv.envConfig.maintenanceMode = true
    render(<GuardedRoutes />, { initialEntries: ["/login"] })
    expect(screen.getByText("Login Content")).toBeInTheDocument()
  })

  it("redirects deeper /auth/* paths during maintenance (auth exemption is exact)", () => {
    // The guard's authPattern only exempts /login, /register, /forgot-password,
    // /reset-password, /verify-email and the exact /auth/ prefix — a deeper
    // path like /auth/mfa-challenge is treated as a public route and is
    // redirected to /maintenance. Documenting the current guard behaviour.
    mockEnv.envConfig.maintenanceMode = true
    render(<GuardedRoutes />, { initialEntries: ["/auth/mfa-challenge"] })
    expect(screen.getByTestId("app-navigate")).toHaveAttribute("data-to", "/maintenance")
    expect(screen.queryByText("Auth MFA Content")).not.toBeInTheDocument()
  })

  it("keeps public error pages (e.g. /500, /offline) accessible during maintenance", () => {
    mockEnv.envConfig.maintenanceMode = true
    render(<GuardedRoutes />, { initialEntries: ["/500"] })
    expect(screen.getByText("Error Page")).toBeInTheDocument()

    render(<GuardedRoutes />, { initialEntries: ["/offline"] })
    expect(screen.getByText("Offline Page")).toBeInTheDocument()
  })
})
