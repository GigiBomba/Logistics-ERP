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
  it("renders 'Security at Operion' heading", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security at Operion")).toBeInTheDocument()
  })

  it("shows security practices cards", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security Practices")).toBeInTheDocument()
    expect(screen.getByText("Data Encryption")).toBeInTheDocument()
    expect(screen.getByText("Access Control")).toBeInTheDocument()
    expect(screen.getByText("Infrastructure Security")).toBeInTheDocument()
    expect(screen.getByText("Compliance")).toBeInTheDocument()
  })

  it("shows responsible disclosure section", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Responsible Disclosure")).toBeInTheDocument()
    expect(screen.getByText("security@operion.com")).toBeInTheDocument()
    expect(screen.getByText(/How to report a vulnerability/i)).toBeInTheDocument()
  })

  it("shows security FAQ", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Security FAQ")).toBeInTheDocument()
    expect(screen.getByText("Where is my data stored?")).toBeInTheDocument()
    expect(screen.getByText("What encryption standards does Operion use?")).toBeInTheDocument()
  })

  it("shows bug bounty placeholder", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Bug Bounty Program")).toBeInTheDocument()
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
  })

  it("shows CTA", () => {
    render(<SecurityPage />)
    expect(screen.getByText("Ready to see Operion in action?")).toBeInTheDocument()
    expect(screen.getByText("Request a demo")).toBeInTheDocument()
  })
})
