import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import VerifyEmailPage from "@/pages/auth/verify-email"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders verification message", () => {
    render(<VerifyEmailPage />)
    expect(screen.getByText("Check your email")).toBeInTheDocument()
    expect(screen.getByText(/we've sent a verification link/i)).toBeInTheDocument()
  })

  it("renders both buttons", () => {
    render(<VerifyEmailPage />)
    expect(screen.getByRole("link", { name: /go to sign in/i })).toHaveAttribute("href", "/login")
    expect(screen.getByRole("link", { name: /contact support/i })).toHaveAttribute("href", "/contact")
  })

  it("renders MailCheck icon", () => {
    const { container } = render(<VerifyEmailPage />)
    const svg = container.querySelector("svg")
    expect(svg).toBeInTheDocument()
  })
})
