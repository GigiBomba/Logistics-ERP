import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { RequireRole } from "@/components/auth/require-role"
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

describe("RequireRole", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows a loading spinner while auth is loading", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ isLoading: true }))
    const { container } = render(
      <RequireRole roles={["admin"]}>
        <span>protected content</span>
      </RequireRole>
    )
    expect(container.querySelector("svg")).toBeInTheDocument()
    expect(screen.queryByText("protected content")).not.toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("redirects to /login when the user is not authenticated", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ user: null }))
    render(
      <RequireRole roles={["admin"]}>
        <span>protected content</span>
      </RequireRole>
    )
    expect(navigateMock).toHaveBeenCalledWith("/login", { replace: true })
    expect(screen.queryByText("protected content")).not.toBeInTheDocument()
  })

  it("renders the fallback when the role is not allowed and a fallback is provided", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: createMockAuthUser({ role: "dispatcher" }) })
    )
    render(
      <RequireRole roles={["admin"]} fallback={<span>no access</span>}>
        <span>protected content</span>
      </RequireRole>
    )
    expect(screen.getByText("no access")).toBeInTheDocument()
    expect(screen.queryByText("protected content")).not.toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("redirects to /dashboard when the role is not allowed and no fallback is provided", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: createMockAuthUser({ role: "dispatcher" }) })
    )
    render(
      <RequireRole roles={["admin"]}>
        <span>protected content</span>
      </RequireRole>
    )
    expect(navigateMock).toHaveBeenCalledWith("/dashboard", { replace: true })
    expect(screen.queryByText("protected content")).not.toBeInTheDocument()
  })

  it("renders children when the user role is allowed", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ user: createMockAuthUser({ role: "admin" }) })
    )
    render(
      <RequireRole roles={["admin", "owner"]}>
        <span>protected content</span>
      </RequireRole>
    )
    expect(screen.getByText("protected content")).toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalled()
  })
})
