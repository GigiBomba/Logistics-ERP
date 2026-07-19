import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import TrustCenterPage from "@/pages/public/trust-center"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("TrustCenterPage", () => {
  it("renders the hero section with title", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Trust Center")).toBeInTheDocument()
  })

  it("renders hero description", () => {
    render(<TrustCenterPage />)
    expect(
      screen.getByText(
        "Transparency and trust are core to Operion. We share what we build, how we build it, and what you can expect as the product evolves."
      )
    ).toBeInTheDocument()
  })

  it("renders stat cards with values", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Open Source")).toBeInTheDocument()
    expect(screen.getByText("Local-First")).toBeInTheDocument()
    expect(screen.getByText("Transparent")).toBeInTheDocument()
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("renders all five tab triggers", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Infrastructure")).toBeInTheDocument()
    expect(screen.getByText("Security")).toBeInTheDocument()
    expect(screen.getByText("Compliance")).toBeInTheDocument()
    expect(screen.getByText("Privacy")).toBeInTheDocument()
    expect(screen.getByText("Reliability")).toBeInTheDocument()
  })

  it("renders infrastructure tab content by default", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Infrastructure Status")).toBeInTheDocument()
  })

  it("renders infrastructure feature cards", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Local-First Architecture")).toBeInTheDocument()
    expect(screen.getByText("Network Security")).toBeInTheDocument()
    expect(screen.getByText("Development Monitoring")).toBeInTheDocument()
    expect(screen.getByText("Data Portability")).toBeInTheDocument()
  })

  it("switches to security tab content on click", () => {
    render(<TrustCenterPage />)
    fireEvent.click(screen.getByText("Security"))
    expect(screen.getByText("Encryption in Transit")).toBeInTheDocument()
    expect(screen.getByText("Authentication")).toBeInTheDocument()
    expect(screen.getByText("Secure by Design")).toBeInTheDocument()
    expect(screen.getByText("Transparent Development")).toBeInTheDocument()
  })

  it("switches to compliance tab content on click", () => {
    render(<TrustCenterPage />)
    fireEvent.click(screen.getByText("Compliance"))
    expect(screen.getByText("Compliance Certifications")).toBeInTheDocument()
  })

  it("switches to privacy tab content on click", () => {
    render(<TrustCenterPage />)
    fireEvent.click(screen.getByText("Privacy"))
    expect(screen.getByText("Data Collection Philosophy")).toBeInTheDocument()
    expect(screen.getByText("Privacy by Design")).toBeInTheDocument()
    expect(screen.getByText("Data Retention")).toBeInTheDocument()
    expect(screen.getByText("Data Deletion")).toBeInTheDocument()
  })

  it("switches to reliability tab content on click", () => {
    render(<TrustCenterPage />)
    fireEvent.click(screen.getByText("Reliability"))
    const reliabilityTexts = screen.getAllByText("Reliability")
    expect(reliabilityTexts.length).toBeGreaterThanOrEqual(2)
  })

  it("renders FAQ section with title", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Trust & Security FAQ")).toBeInTheDocument()
  })

  it("renders FAQ questions", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Is Operion currently in production?")).toBeInTheDocument()
    expect(screen.getByText("How is my data handled during development?")).toBeInTheDocument()
    expect(screen.getByText("Can I see the source code?")).toBeInTheDocument()
  })

  it("renders responsible disclosure section", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Responsible Disclosure")).toBeInTheDocument()
    expect(screen.getByText(/security@operion\.com/)).toBeInTheDocument()
  })

  it("renders security badges", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("48h acknowledgment")).toBeInTheDocument()
    expect(screen.getByText("Safe harbor")).toBeInTheDocument()
    expect(screen.getByText("No legal action")).toBeInTheDocument()
  })

  it("renders CTA banner section", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Need more details?")).toBeInTheDocument()
    expect(screen.getByText("Contact security")).toBeInTheDocument()
  })

  it("renders callout with infrastructure status info", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("Infrastructure Status")).toBeInTheDocument()
  })

  it("renders how to report a vulnerability section", () => {
    render(<TrustCenterPage />)
    expect(screen.getByText("How to Report a Vulnerability")).toBeInTheDocument()
  })
})
