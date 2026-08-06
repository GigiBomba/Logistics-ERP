import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import ResetPasswordPage from "@/pages/auth/reset-password"
import { authApi } from "@/api/endpoints"
import { toast } from "sonner"

const navigateMock = vi.fn()

vi.mock("@/hooks/useAppNavigate", () => ({
  useAppNavigate: () => navigateMock,
}))

vi.mock("@/api/endpoints", () => ({
  authApi: { resetPassword: vi.fn() },
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock.mockReset()
  })

  it("shows invalid link card when no token", () => {
    render(<ResetPasswordPage />)
    expect(screen.getByText("Invalid Reset Link")).toBeInTheDocument()
    expect(screen.getByText(/this password reset link is invalid/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /request new link/i })).toHaveAttribute("href", "/forgot-password")
  })

  it("shows the password form when a token is present", () => {
    render(<ResetPasswordPage />, { initialEntries: ["/reset-password?token=abc123"] })
    expect(screen.getByText("Set new password")).toBeInTheDocument()
    expect(screen.getByLabelText("New Password")).toBeInTheDocument()
    expect(screen.getByLabelText("Confirm New Password")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /reset password/i })).toBeInTheDocument()
  })

  it("shows validation errors for short/mismatched passwords", async () => {
    const user = userEvent.setup()
    render(<ResetPasswordPage />, { initialEntries: ["/reset-password?token=abc123"] })
    await user.type(screen.getByLabelText("New Password"), "short")
    await user.type(screen.getByLabelText("Confirm New Password"), "different")
    await user.click(screen.getByRole("button", { name: /reset password/i }))

    expect(await screen.findByText("Password must be at least 8 characters")).toBeInTheDocument()
    expect(screen.getByText("Passwords don't match")).toBeInTheDocument()
    expect(authApi.resetPassword).not.toHaveBeenCalled()
  })

  it("resets the password and navigates to /login on success", async () => {
    vi.mocked(authApi.resetPassword).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()
    render(<ResetPasswordPage />, { initialEntries: ["/reset-password?token=abc123"] })
    await user.type(screen.getByLabelText("New Password"), "new-secure-pass")
    await user.type(screen.getByLabelText("Confirm New Password"), "new-secure-pass")
    await user.click(screen.getByRole("button", { name: /reset password/i }))

    await waitFor(() => {
      expect(authApi.resetPassword).toHaveBeenCalledWith("abc123", "new-secure-pass")
    })
    expect(toast.success).toHaveBeenCalledWith("Password reset successfully! You can now sign in.")
    expect(navigateMock).toHaveBeenCalledWith("/login")
  })

  it("shows an error toast when the reset fails", async () => {
    vi.mocked(authApi.resetPassword).mockRejectedValue(new Error("expired"))
    const user = userEvent.setup()
    render(<ResetPasswordPage />, { initialEntries: ["/reset-password?token=abc123"] })
    await user.type(screen.getByLabelText("New Password"), "new-secure-pass")
    await user.type(screen.getByLabelText("Confirm New Password"), "new-secure-pass")
    await user.click(screen.getByRole("button", { name: /reset password/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Failed to reset password. The link may have expired."
      )
    })
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("toggles the new password visibility", async () => {
    const user = userEvent.setup()
    render(<ResetPasswordPage />, { initialEntries: ["/reset-password?token=abc123"] })
    const password = screen.getByLabelText("New Password")
    expect(password).toHaveAttribute("type", "password")
    const toggles = screen
      .getAllByRole("button")
      .filter((b) => b !== screen.getByRole("button", { name: /reset password/i }))
    await user.click(toggles[0])
    expect(password).toHaveAttribute("type", "text")
  })

  it("toggles the confirm password visibility", async () => {
    const user = userEvent.setup()
    render(<ResetPasswordPage />, { initialEntries: ["/reset-password?token=abc123"] })
    const confirm = screen.getByLabelText("Confirm New Password")
    expect(confirm).toHaveAttribute("type", "password")
    const toggles = screen
      .getAllByRole("button")
      .filter((b) => b !== screen.getByRole("button", { name: /reset password/i }))
    await user.click(toggles[1])
    expect(confirm).toHaveAttribute("type", "text")
  })
})
