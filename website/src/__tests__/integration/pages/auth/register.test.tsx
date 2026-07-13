import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import RegisterPage from "@/pages/auth/register"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthContext } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

describe("RegisterPage", () => {
  const mockRegister = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ register: mockRegister })
    )
  })

  it("renders registration form", () => {
    render(<RegisterPage />)
    expect(screen.getByText("Create your account")).toBeInTheDocument()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument()
  })

  it("renders link to login", () => {
    render(<RegisterPage />)
    expect(screen.getByText(/already have an account/i)).toBeInTheDocument()
    expect(screen.getByText(/sign in/i)).toHaveAttribute("href", "/login")
  })
})
