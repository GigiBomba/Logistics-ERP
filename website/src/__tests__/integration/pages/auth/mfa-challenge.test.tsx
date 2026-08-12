import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import MfaChallengePage from "@/pages/auth/mfa-challenge"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthContext } from "@/test-utils"

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

const navigateMock = vi.fn()

vi.mock("@/hooks/useAppNavigate", () => ({
  useAppNavigate: () => navigateMock,
}))

describe("MfaChallengePage", () => {
  const mockVerifyMfa = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock.mockReset()
    vi.mocked(useAuth).mockReturnValue(
      createMockAuthContext({ mfaSessionToken: "sess-1", verifyMfa: mockVerifyMfa })
    )
  })

  it("redirects to /login when there is no MFA session token", () => {
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ mfaSessionToken: null }))
    const { container } = render(<MfaChallengePage />)
    expect(navigateMock).toHaveBeenCalledWith("/login", { replace: true })
    expect(container.firstChild).toBeNull()
  })

  it("renders the challenge form with a session token", () => {
    render(<MfaChallengePage />)
    expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /verify/i })).toBeInTheDocument()
    expect(screen.getByText(/use a backup code/i)).toBeInTheDocument()
  })

  it("does not enable submit until 6 digits are entered", async () => {
    const user = userEvent.setup()
    render(<MfaChallengePage />)
    const input = screen.getByLabelText(/verification code/i)
    const submit = screen.getByRole("button", { name: /verify/i }) as HTMLButtonElement
    expect(submit.disabled).toBe(true)
    await user.type(input, "123")
    expect(submit.disabled).toBe(true)
  })

  it("only allows digits and caps at 6 characters", async () => {
    const user = userEvent.setup()
    render(<MfaChallengePage />)
    const input = screen.getByLabelText(/verification code/i) as HTMLInputElement
    await user.type(input, "12ab34cd56")
    await waitFor(() => expect(input.value).toBe("123456"))
  })

  it("verifies the code and navigates to /dashboard on success", async () => {
    mockVerifyMfa.mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<MfaChallengePage />)
    const input = screen.getByLabelText(/verification code/i)
    await user.type(input, "123456")

    await waitFor(() => {
      expect(mockVerifyMfa).toHaveBeenCalledWith("123456")
    })
    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/dashboard", { replace: true })
    })
  })

  it("shows an error when the verification code is invalid", async () => {
    mockVerifyMfa.mockRejectedValue(new Error("invalid"))
    const user = userEvent.setup()
    render(<MfaChallengePage />)
    const input = screen.getByLabelText(/verification code/i)
    await user.type(input, "000000")

    await waitFor(() => {
      expect(screen.getAllByText(/invalid verification code/i).length).toBeGreaterThan(0)
    })
    expect(input).toHaveValue("")
  })

  it("switches to backup code mode and back", async () => {
    const user = userEvent.setup()
    render(<MfaChallengePage />)
    await user.click(screen.getByRole("button", { name: /use a backup code instead/i }))
    expect(screen.getByLabelText(/backup code/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /use authenticator app instead/i })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /use authenticator app instead/i }))
    expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument()
  })

  it("submits via the form when 6 digits are present", async () => {
    mockVerifyMfa.mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(<MfaChallengePage />)
    const input = screen.getByLabelText(/verification code/i)
    await user.type(input, "654321")
    await waitFor(() => {
      expect(mockVerifyMfa).toHaveBeenCalledWith("654321")
    })
  })
})
