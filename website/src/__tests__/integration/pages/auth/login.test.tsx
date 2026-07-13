import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import LoginPage from "@/pages/auth/login"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthContext } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

describe("LoginPage", () => {
  const mockLogin = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ login: mockLogin })
    )
  })

  it("renders login form", () => {
    render(<LoginPage />)
    expect(screen.getByText("Welcome back")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toBeInTheDocument()
    expect(screen.getByLabelText("Password")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument()
  })

  it("renders links to register and forgot password", () => {
    render(<LoginPage />)
    expect(screen.getByText(/don't have an account/i)).toBeInTheDocument()
    expect(screen.getByText(/sign up/i)).toHaveAttribute("href", "/register")
    expect(screen.getByText(/forgot password/i)).toHaveAttribute("href", "/forgot-password")
  })
})
