import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor, fireEvent, act } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import LoginPage from "@/pages/auth/login"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthContext } from "@/test-utils"
import { toast } from "sonner"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

const navigateMock = vi.fn()

vi.mock("@/hooks/useAppNavigate", () => ({
  useAppNavigate: () => navigateMock,
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

// Controllable turnstile mock so tests can simulate verification.
const { turnstilePropsRef } = vi.hoisted(() => ({ turnstilePropsRef: { current: null as any } }))

vi.mock("@/components/shared/turnstile-widget", () => ({
  default: (props: any) => {
    turnstilePropsRef.current = props
    return <div data-testid="mock-turnstile" />
  },
}))

function getForm(container: HTMLElement): HTMLFormElement {
  const form = container.querySelector("form")
  if (!form) throw new Error("form not found")
  return form as HTMLFormElement
}

function typeCredentials(user: ReturnType<typeof userEvent.setup>, email: string, password: string) {
  return user.type(screen.getByLabelText("Email"), email).then(() =>
    user.type(screen.getByLabelText("Password"), password)
  )
}

describe("LoginPage", () => {
  const mockLogin = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    turnstilePropsRef.current = null
    navigateMock.mockReset()
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ login: mockLogin }))
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

  it("shows validation errors for invalid email and empty password", async () => {
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await user.type(screen.getByLabelText("Email"), "not-an-email")
    fireEvent.submit(getForm(container))
    expect(await screen.findByText("Please enter a valid email")).toBeInTheDocument()
    expect(await screen.findByText("Password is required")).toBeInTheDocument()
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it("navigates to /dashboard on successful login", async () => {
    mockLogin.mockResolvedValue({ mfaRequired: false })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("user@operionerp.xyz", "correct-password", false, "")
    })
    expect(navigateMock).toHaveBeenCalledWith("/dashboard", { replace: true })
    expect(toast.success).toHaveBeenCalled()
  })

  it("navigates to a safe returnUrl after login", async () => {
    mockLogin.mockResolvedValue({ mfaRequired: false })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />, {
      initialEntries: ["/login?returnUrl=/dashboard/reports"],
    })
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    fireEvent.submit(getForm(container))

    await waitFor(() => expect(navigateMock).toHaveBeenCalled())
    expect(navigateMock).toHaveBeenCalledWith("/dashboard/reports", { replace: true })
  })

  it("ignores unsafe returnUrls (external or protocol-relative)", async () => {
    mockLogin.mockResolvedValue({ mfaRequired: false })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />, {
      initialEntries: ["/login?returnUrl=https%3A%2F%2Fevil.example%2Fphish"],
    })
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    fireEvent.submit(getForm(container))
    await waitFor(() => expect(navigateMock).toHaveBeenCalled())
    expect(navigateMock).toHaveBeenCalledWith("/dashboard", { replace: true })
  })

  it("redirects to the MFA challenge page when MFA is required", async () => {
    mockLogin.mockResolvedValue({ mfaRequired: true })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/auth/mfa-challenge", { replace: true })
    })
    expect(toast.success).not.toHaveBeenCalled()
  })

  it("shows a rate-limit error when the API returns 429", async () => {
    mockLogin.mockRejectedValue({ response: { status: 429, data: { detail: "Slow down please" } } })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    fireEvent.submit(getForm(container))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Slow down please"))
  })

  it("falls back to the generic rate-limit message when 429 has no detail", async () => {
    mockLogin.mockRejectedValue({ response: { status: 429, data: {} } })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Too many login attempts. Please try again later."
      )
    })
  })

  it("shows a generic invalid credentials error otherwise", async () => {
    mockLogin.mockRejectedValue({ response: { status: 400, data: { detail: "nope" } } })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Invalid email or password. Please try again.")
    })
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("passes the turnstile token to login", async () => {
    mockLogin.mockResolvedValue({ mfaRequired: false })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    act(() => turnstilePropsRef.current.onVerify("tok-xyz"))
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("user@operionerp.xyz", "correct-password", false, "tok-xyz")
    })
  })

  it("clears the turnstile token when it expires", async () => {
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    act(() => {
      turnstilePropsRef.current.onVerify("tok-xyz")
      turnstilePropsRef.current.onExpired()
    })
    await typeCredentials(user, "a@b.com", "secret-password")
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("a@b.com", "secret-password", false, "")
    })
  })

  it("toggles the password visibility", () => {
    const { container } = render(<LoginPage />)
    const password = screen.getByLabelText("Password")
    expect(password).toHaveAttribute("type", "password")
    const toggle = screen
      .getAllByRole("button")
      .find((b) => b !== screen.getByRole("button", { name: /sign in/i }))!
    fireEvent.click(toggle)
    expect(password).toHaveAttribute("type", "text")
    fireEvent.click(toggle)
    expect(password).toHaveAttribute("type", "password")
    expect(container).toBeTruthy()
  })

  it("toggles the remember me checkbox", async () => {
    const user = userEvent.setup()
    render(<LoginPage />)
    const checkbox = screen.getByRole("checkbox", { name: /remember me/i })
    await user.click(checkbox)
    expect(checkbox).toBeChecked()
  })

  it("submits rememberMe true when the checkbox is checked", async () => {
    mockLogin.mockResolvedValue({ mfaRequired: false })
    const user = userEvent.setup()
    const { container } = render(<LoginPage />)
    await typeCredentials(user, "user@operionerp.xyz", "correct-password")
    await user.click(screen.getByRole("checkbox", { name: /remember me/i }))
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("user@operionerp.xyz", "correct-password", true, "")
    })
  })
})
