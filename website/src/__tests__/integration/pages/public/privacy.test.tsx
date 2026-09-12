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
    // Each title appears twice: once in the table of contents and once as the section heading
    expect(screen.getAllByText("1. Information We Collect")).toHaveLength(2)
    expect(screen.getAllByText("2. How We Use Information")).toHaveLength(2)
    expect(screen.getAllByText("3. Data Storage & Security")).toHaveLength(2)
    expect(screen.getAllByText("4. Data Sharing")).toHaveLength(2)
    expect(screen.getAllByText("5. Your Rights")).toHaveLength(2)
    expect(screen.getAllByText("6. Cookies")).toHaveLength(2)
    expect(screen.getAllByText("7. Contact Us")).toHaveLength(2)
  })

  it("renders policy content text", () => {
    render(<PrivacyPage />)
    expect(screen.getByText(/AES-256 encryption at rest/i)).toBeInTheDocument()
    expect(screen.getByText(/TLS 1.3 for data in transit/i)).toBeInTheDocument()
    expect(screen.getAllByText(/privacy@operionerp.xyz/i).length).toBeGreaterThanOrEqual(1)
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
