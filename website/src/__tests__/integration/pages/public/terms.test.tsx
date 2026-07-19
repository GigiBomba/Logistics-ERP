import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import TermsPage from "@/pages/public/terms"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("TermsPage", () => {
  it("renders the page title", () => {
    render(<TermsPage />)
    expect(screen.getByText("Terms of Service")).toBeInTheDocument()
  })

  it("shows last updated date", () => {
    render(<TermsPage />)
    expect(screen.getByText(/last updated.*july 2026/i)).toBeInTheDocument()
  })

  it("renders table of contents", () => {
    render(<TermsPage />)
    expect(screen.getByText("Table of Contents")).toBeInTheDocument()
  })

  it("renders all 10 terms sections", () => {
    render(<TermsPage />)
    expect(screen.getByText("1. Acceptance of Terms")).toBeInTheDocument()
    expect(screen.getByText("2. Account Registration & Security")).toBeInTheDocument()
    expect(screen.getByText("3. Subscription & Payment Terms")).toBeInTheDocument()
    expect(screen.getByText("4. License Grant & Restrictions")).toBeInTheDocument()
    expect(screen.getByText("5. Acceptable Use Policy")).toBeInTheDocument()
    expect(screen.getByText("6. Intellectual Property")).toBeInTheDocument()
    expect(screen.getByText("7. Limitation of Liability")).toBeInTheDocument()
    expect(screen.getByText("8. Termination")).toBeInTheDocument()
    expect(screen.getByText("9. Governing Law")).toBeInTheDocument()
    expect(screen.getByText("10. Changes to Terms")).toBeInTheDocument()
  })

  it("renders key content from the terms", () => {
    render(<TermsPage />)
    expect(screen.getByText(/non-exclusive, non-transferable, limited license/i)).toBeInTheDocument()
    expect(screen.getByText(/laws of Romania/i)).toBeInTheDocument()
  })

  it("renders table of contents links with correct hrefs", () => {
    render(<TermsPage />)
    const tocLinks = screen.getAllByRole("link")
    const tocHrefs = tocLinks.map((l) => l.getAttribute("href"))
    expect(tocHrefs).toContain("#acceptance")
    expect(tocHrefs).toContain("#account")
    expect(tocHrefs).toContain("#subscription")
    expect(tocHrefs).toContain("#license")
    expect(tocHrefs).toContain("#acceptable-use")
    expect(tocHrefs).toContain("#intellectual-property")
    expect(tocHrefs).toContain("#liability")
    expect(tocHrefs).toContain("#termination")
    expect(tocHrefs).toContain("#governing-law")
    expect(tocHrefs).toContain("#changes")
  })
})
