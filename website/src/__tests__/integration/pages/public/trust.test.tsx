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
    expect(screen.getByText("Secure by Design")).toBeInTheDocument()
    expect(screen.getByText("Access Control")).toBeInTheDocument()
    expect(screen.getByText("Transparency")).toBeInTheDocument()
    expect(screen.getByText("Future Auditing")).toBeInTheDocument()
  })

  it("renders compliance section", () => {
    render(<TrustPage />)
    expect(screen.getByText("Compliance")).toBeInTheDocument()
  })

  it("renders call-to-action", () => {
    render(<TrustPage />)
    expect(screen.getByText("Have questions?")).toBeInTheDocument()
  })

  it("links to the browsable /dpa page and keeps the draft-template download", () => {
    render(<TrustPage />)
    // Primary action navigates to the rendered DPA document page.
    const viewLink = screen.getByRole("link", { name: "Data Processing Agreement (DPA)" })
    expect(viewLink).toHaveAttribute("href", "/dpa")
    // Secondary action keeps the raw DRAFT TEMPLATE download available. A
    // clearly-marked DRAFT TEMPLATE ships at public/dpa/operion-dpa.md so the
    // link is functional today; the `download` attribute makes the draft download.
    // When counsel delivers website/public/dpa/operion-dpa.pdf, flip DPA_HREF.
    const downloadLink = screen.getByRole("link", { name: "Download DPA template" })
    expect(downloadLink).toHaveAttribute("href", "/dpa/operion-dpa.md")
    expect(downloadLink).toHaveAttribute("download")
  })
})
