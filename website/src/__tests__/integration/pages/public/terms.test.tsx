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
    // Each title appears twice: once in the table of contents and once as the section heading
    expect(screen.getAllByText("1. Acceptance of Terms")).toHaveLength(2)
    expect(screen.getAllByText("2. Account Registration & Security")).toHaveLength(2)
    expect(screen.getAllByText("3. Subscription & Payment Terms")).toHaveLength(2)
    expect(screen.getAllByText("4. License Grant & Restrictions")).toHaveLength(2)
    expect(screen.getAllByText("5. Acceptable Use Policy")).toHaveLength(2)
    expect(screen.getAllByText("6. Intellectual Property")).toHaveLength(2)
    expect(screen.getAllByText("7. Limitation of Liability")).toHaveLength(2)
    expect(screen.getAllByText("8. Termination")).toHaveLength(2)
    expect(screen.getAllByText("9. Governing Law")).toHaveLength(2)
    expect(screen.getAllByText("10. Changes to Terms")).toHaveLength(2)
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
