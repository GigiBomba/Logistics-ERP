import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import SecurityPage from "@/pages/public/security"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("SecurityPage", () => {
  it("renders heading", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security at Operion")).toBeInTheDocument()
  })

  it("shows security practices section", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security Practices")).toBeInTheDocument()
    expect(screen.getByText("Security Features")).toBeInTheDocument()
  })

  it("shows responsible disclosure section", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Responsible Disclosure")).toBeInTheDocument()
  })

  it("shows security FAQ", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security FAQ")).toBeInTheDocument()
  })

  it("shows bug bounty placeholder", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Bug Bounty Program")).toBeInTheDocument()
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
  })

  it("shows CTA", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Ready to dispatch with a single instruction?")).toBeInTheDocument()
    expect(screen.getByText("Get Started")).toBeInTheDocument()
  })
})
