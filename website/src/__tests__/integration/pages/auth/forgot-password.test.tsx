import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor, fireEvent } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import ForgotPasswordPage from "@/pages/auth/forgot-password"
import { authApi } from "@/api/endpoints"
import { toast } from "sonner"
import { AxiosError } from "axios"

vi.mock("@/api/endpoints", () => ({
  authApi: { forgotPassword: vi.fn() },
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const { motionMock } = vi.hoisted(() => {
  const MockMotionDiv = ({ children, ...rest }: any) => <div {...rest}>{children}</div>
  return {
    motionMock: new Proxy({}, { get: () => MockMotionDiv }),
  }
})

vi.mock("motion/react", () => ({
  motion: motionMock,
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

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

  it("renders link back to login", () => {
    render(<ForgotPasswordPage />)
    expect(screen.getByText(/remember your password/i)).toBeInTheDocument()
    expect(screen.getByText(/sign in/i)).toBeInTheDocument()
  })

  it("shows a validation error for an invalid email", async () => {
    const user = userEvent.setup()
    const { container } = render(<ForgotPasswordPage />)
    await user.type(screen.getByLabelText("Email"), "nope")
    const form = container.querySelector("form") as HTMLFormElement
    fireEvent.submit(form)
    expect(await screen.findByText("Please enter a valid email")).toBeInTheDocument()
    expect(authApi.forgotPassword).not.toHaveBeenCalled()
  })

  it("sends the reset link and shows a success toast", async () => {
    vi.mocked(authApi.forgotPassword).mockResolvedValue({ data: { status: "ok" } } as any)
    const user = userEvent.setup()
    render(<ForgotPasswordPage />)
    await user.type(screen.getByLabelText("Email"), "user@operionerp.xyz")
    await user.click(screen.getByRole("button", { name: /send reset link/i }))

    await waitFor(() => {
      expect(authApi.forgotPassword).toHaveBeenCalledWith("user@operionerp.xyz")
    })
    expect(toast.success).toHaveBeenCalledWith("If an account exists, a reset link has been sent.")
  })

  it("shows a rate-limit toast when the API returns 429", async () => {
    const err = new AxiosError("Too many", "ERR_BAD_RESPONSE")
    err.response = { status: 429, data: { detail: "Slow down" }, statusText: "x", headers: {}, config: {} as any }
    vi.mocked(authApi.forgotPassword).mockRejectedValue(err)
    const user = userEvent.setup()
    render(<ForgotPasswordPage />)
    await user.type(screen.getByLabelText("Email"), "user@operionerp.xyz")
    await user.click(screen.getByRole("button", { name: /send reset link/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Too many login attempts. Please try again later.")
    })
  })

  it("shows a generic failure toast for other errors", async () => {
    vi.mocked(authApi.forgotPassword).mockRejectedValue(new Error("network"))
    const user = userEvent.setup()
    render(<ForgotPasswordPage />)
    await user.type(screen.getByLabelText("Email"), "user@operionerp.xyz")
    await user.click(screen.getByRole("button", { name: /send reset link/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Failed to reset password. The link may have expired."
      )
    })
  })
})
