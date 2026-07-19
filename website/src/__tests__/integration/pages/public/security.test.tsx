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

  it("shows security practices", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security Practices")).toBeInTheDocument()
    expect(screen.getByText("Encryption in Transit")).toBeInTheDocument()
    expect(screen.getByText("Access Control")).toBeInTheDocument()
  })

  it("shows security FAQ", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security FAQ")).toBeInTheDocument()
  })

  it("shows CTA", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Ready to see Operion in action?")).toBeInTheDocument()
  })
})
