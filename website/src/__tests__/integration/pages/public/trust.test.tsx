import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import TrustPage from "@/pages/public/trust"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("TrustPage", () => {
  it("renders heading", () => {
    render(<TrustPage />)
    expect(screen.getByText("Trust Center")).toBeInTheDocument()
  })

  it("renders security overview cards", () => {
    render(<TrustPage />)
    expect(screen.getByText("Encryption")).toBeInTheDocument()
    expect(screen.getByText("Access Control")).toBeInTheDocument()
    expect(screen.getByText("Monitoring")).toBeInTheDocument()
    expect(screen.getByText("Penetration Testing")).toBeInTheDocument()
  })

  it("renders compliance section", () => {
    render(<TrustPage />)
    expect(screen.getByText("Compliance")).toBeInTheDocument()
  })

  it("renders call-to-action", () => {
    render(<TrustPage />)
    expect(screen.getByText(/need more details/i)).toBeInTheDocument()
  })
})
