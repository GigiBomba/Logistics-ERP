import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import ForgotPasswordPage from "@/pages/auth/forgot-password"

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders forgot password form", () => {
    render(<ForgotPasswordPage />)
    expect(screen.getByText("Reset Password")).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /send reset link/i })).toBeInTheDocument()
  })

  it("renders link back to home", () => {
    render(<ForgotPasswordPage />)
    expect(screen.getByText(/remember your password/i)).toBeInTheDocument()
  })
})
