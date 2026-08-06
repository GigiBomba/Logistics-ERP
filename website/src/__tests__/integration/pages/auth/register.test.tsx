import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor, fireEvent, act } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import RegisterPage from "@/pages/auth/register"
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

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/full name/i), "Jane Doe")
  await user.type(screen.getByLabelText("Email"), "jane@operionerp.xyz")
  await user.type(screen.getByLabelText("Password"), "strong-pass-123")
  await user.type(screen.getByLabelText("Confirm Password"), "strong-pass-123")
  await user.click(screen.getByRole("checkbox", { name: /i accept the terms of service/i }))
}

describe("RegisterPage", () => {
  const mockRegister = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    turnstilePropsRef.current = null
    navigateMock.mockReset()
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ register: mockRegister }))
  })

  it("renders registration form", () => {
    render(<RegisterPage />)
    expect(screen.getByText("Create Account")).toBeInTheDocument()
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Email")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /^create$/i })).toBeInTheDocument()
  })

  it("renders link to login", () => {
    render(<RegisterPage />)
    expect(screen.getByText(/already have an account/i)).toBeInTheDocument()
    expect(screen.getByText(/sign in/i)).toHaveAttribute("href", "/login")
  })

  it("shows validation errors for an incomplete form", async () => {
    const user = userEvent.setup()
    const { container } = render(<RegisterPage />)
    await user.type(screen.getByLabelText("Email"), "bad-email")
    await user.type(screen.getByLabelText("Password"), "short")
    await user.type(screen.getByLabelText("Confirm Password"), "different")
    fireEvent.submit(getForm(container))

    expect(await screen.findByText("Name must be at least 2 characters")).toBeInTheDocument()
    expect(screen.getByText("Please enter a valid email")).toBeInTheDocument()
    expect(screen.getByText("Password must be at least 8 characters")).toBeInTheDocument()
    expect(screen.getByText("You must accept the Terms and Privacy Policy")).toBeInTheDocument()
    expect(mockRegister).not.toHaveBeenCalled()
  })

  it("shows a password mismatch error when only the passwords differ", async () => {
    const user = userEvent.setup()
    render(<RegisterPage />)
    await user.type(screen.getByLabelText(/full name/i), "Jane Doe")
    await user.type(screen.getByLabelText("Email"), "jane@operionerp.xyz")
    await user.type(screen.getByLabelText("Password"), "strong-pass-123")
    await user.type(screen.getByLabelText("Confirm Password"), "other-pass-456")
    await user.click(screen.getByRole("checkbox", { name: /i accept the terms of service/i }))
    await user.click(screen.getByRole("button", { name: /^create$/i }))

    expect(await screen.findByText("Passwords don't match")).toBeInTheDocument()
    expect(mockRegister).not.toHaveBeenCalled()
  })

  it("registers a user and navigates to /verify-email", async () => {
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<RegisterPage />)
    await fillValidForm(user)
    await user.click(screen.getByRole("button", { name: /^create$/i }))

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Jane Doe",
          email: "jane@operionerp.xyz",
          password: "strong-pass-123",
        })
      )
    })
    expect(toast.success).toHaveBeenCalledWith("Account created! Check your email to verify.")
    expect(navigateMock).toHaveBeenCalledWith("/verify-email")
  })

  it("passes the turnstile token when provided", async () => {
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<RegisterPage />)
    await fillValidForm(user)
    act(() => turnstilePropsRef.current.onVerify("tok-reg"))
    await user.click(screen.getByRole("button", { name: /^create$/i }))

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith(
        expect.objectContaining({ turnstile_token: "tok-reg" })
      )
    })
  })

  it("shows a rate-limit referral error on 429", async () => {
    mockRegister.mockRejectedValue({ response: { status: 429, data: {} } })
    const user = userEvent.setup()
    const { container } = render(<RegisterPage />)
    await fillValidForm(user)
    fireEvent.submit(getForm(container))

    expect(
      await screen.findByText(/too many redemptions for this code today/i)
    ).toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("shows a self-referral error from the backend detail", async () => {
    mockRegister.mockRejectedValue({
      response: { status: 400, data: { detail: "You cannot refer yourself" } },
    })
    const user = userEvent.setup()
    const { container } = render(<RegisterPage />)
    await fillValidForm(user)
    fireEvent.submit(getForm(container))

    expect(await screen.findByText(/cannot refer yourself/i)).toBeInTheDocument()
  })

  it("shows a generic registration error for other failures", async () => {
    mockRegister.mockRejectedValue(new Error("network"))
    const user = userEvent.setup()
    const { container } = render(<RegisterPage />)
    await fillValidForm(user)
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Registration failed. Please try again.")
    })
  })

  it("pre-fills the referral code from the URL", () => {
    render(<RegisterPage />, { initialEntries: ["/register?ref=REF42"] })
    expect(screen.getByLabelText(/referral code/i)).toHaveValue("REF42")
  })

  it("toggles password field visibility", () => {
    render(<RegisterPage />)
    const password = screen.getByLabelText("Password")
    expect(password).toHaveAttribute("type", "password")
    const toggles = screen
      .getAllByRole("button")
      .filter((b) => b !== screen.getByRole("button", { name: /^create$/i }))
    fireEvent.click(toggles[0])
    expect(password).toHaveAttribute("type", "text")
    fireEvent.click(toggles[0])
    expect(password).toHaveAttribute("type", "password")
  })

  it("toggles the confirm password field visibility", () => {
    render(<RegisterPage />)
    const confirm = screen.getByLabelText("Confirm Password")
    expect(confirm).toHaveAttribute("type", "password")
    const toggles = screen
      .getAllByRole("button")
      .filter((b) => b !== screen.getByRole("button", { name: /^create$/i }))
    fireEvent.click(toggles[1])
    expect(confirm).toHaveAttribute("type", "text")
  })

  it("clears the turnstile token when it expires", async () => {
    mockRegister.mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<RegisterPage />)
    await fillValidForm(user)
    act(() => {
      turnstilePropsRef.current.onVerify("tok-reg")
      turnstilePropsRef.current.onExpired()
    })
    await user.click(screen.getByRole("button", { name: /^create$/i }))

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith(
        expect.objectContaining({ turnstile_token: undefined })
      )
    })
  })

  it("shows the password strength indicator while typing", async () => {
    const user = userEvent.setup()
    render(<RegisterPage />)
    await user.type(screen.getByLabelText("Password"), "weak")
    expect(screen.getByText(/strength|weak|strong/i)).toBeInTheDocument()
  })
})
