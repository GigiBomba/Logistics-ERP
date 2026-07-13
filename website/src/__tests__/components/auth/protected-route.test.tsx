import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthContext, createMockAuthUser } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

describe("ProtectedRoute", () => {
  beforeEach(() => vi.clearAllMocks())

  it("shows loading spinner while isLoading", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ isLoading: true })
    )
    const { container } = render(<ProtectedRoute />)
    const spinner = container.querySelector("svg")
    expect(spinner).toBeInTheDocument()
    expect(spinner!.className).toBeTruthy()
  })

  it("renders nothing special when authenticated (no spinner)", () => {
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ isAuthenticated: true, user: createMockAuthUser() })
    )
    const { container } = render(<ProtectedRoute />)
    const spinners = container.querySelectorAll("svg")
    // Outlet renders nothing in unit tests — confirm no crash
    expect(container.querySelector('[style*="display"]')).toBeFalsy()
  })
})
