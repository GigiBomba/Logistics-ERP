import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import PrivacyPage from "@/pages/public/privacy"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("PrivacyPage", () => {
  it("renders the page title", () => {
    render(<PrivacyPage />)
    expect(screen.getByText("Privacy Policy")).toBeInTheDocument()
  })

  it("shows last updated date", () => {
    render(<PrivacyPage />)
    expect(screen.getByText(/last updated.*july 2026/i)).toBeInTheDocument()
  })

  it("renders table of contents", () => {
    render(<PrivacyPage />)
    expect(screen.getByText("Table of Contents")).toBeInTheDocument()
  })

  it("renders all 7 privacy policy sections", () => {
    render(<PrivacyPage />)
    expect(screen.getByText("1. Information We Collect")).toBeInTheDocument()
    expect(screen.getByText("2. How We Use Information")).toBeInTheDocument()
    expect(screen.getByText("3. Data Storage & Security")).toBeInTheDocument()
    expect(screen.getByText("4. Data Sharing")).toBeInTheDocument()
    expect(screen.getByText("5. Your Rights")).toBeInTheDocument()
    expect(screen.getByText("6. Cookies")).toBeInTheDocument()
    expect(screen.getByText("7. Contact Us")).toBeInTheDocument()
  })

  it("renders policy content text", () => {
    render(<PrivacyPage />)
    expect(screen.getByText(/AES-256 encryption at rest/i)).toBeInTheDocument()
    expect(screen.getByText(/TLS 1.3 for data in transit/i)).toBeInTheDocument()
    expect(screen.getByText(/privacy@operion.com/i)).toBeInTheDocument()
  })

  it("renders table of contents links with correct hrefs", () => {
    render(<PrivacyPage />)
    const tocLinks = screen.getAllByRole("link")
    const tocHrefs = tocLinks.map((l) => l.getAttribute("href"))
    expect(tocHrefs).toContain("#information-collection")
    expect(tocHrefs).toContain("#information-use")
    expect(tocHrefs).toContain("#data-storage")
    expect(tocHrefs).toContain("#data-sharing")
    expect(tocHrefs).toContain("#your-rights")
    expect(tocHrefs).toContain("#cookies")
    expect(tocHrefs).toContain("#contact")
  })
})
