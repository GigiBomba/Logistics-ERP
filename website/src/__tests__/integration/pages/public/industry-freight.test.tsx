import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IndustryFreightPage from "@/pages/public/industry-freight"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IndustryFreightPage", () => {
  it("renders page header with title", () => {
    render(<IndustryFreightPage />)
    expect(screen.getByText("Operion for Freight Forwarders")).toBeInTheDocument()
  })

  it("renders challenges section with freight-specific challenges", () => {
    render(<IndustryFreightPage />)
    expect(screen.getByText("Industry Challenges")).toBeInTheDocument()
    expect(screen.getByText("Load Matching")).toBeInTheDocument()
    expect(screen.getByText("Documentation")).toBeInTheDocument()
    expect(screen.getByText("Multi-Leg Trips")).toBeInTheDocument()
    expect(screen.getByText("Customs Compliance")).toBeInTheDocument()
  })

  it("renders solutions section with freight/logistics capabilities", () => {
    render(<IndustryFreightPage />)
    expect(screen.getByText("How Operion Helps")).toBeInTheDocument()
    expect(screen.getByText("CMR Automation")).toBeInTheDocument()
    expect(screen.getByText("Load Optimization")).toBeInTheDocument()
    expect(screen.getByText("Document OCR")).toBeInTheDocument()
    expect(screen.getByText("Trip Planning")).toBeInTheDocument()
  })

  it("renders workflow section", () => {
    render(<IndustryFreightPage />)
    expect(screen.getByText("Workflow Example")).toBeInTheDocument()
    expect(screen.getByText("Receive Order")).toBeInTheDocument()
    expect(screen.getByText("Match Load")).toBeInTheDocument()
    expect(screen.getByText("Generate Docs")).toBeInTheDocument()
    expect(screen.getByText("Track Shipment")).toBeInTheDocument()
    expect(screen.getByText("Clear Customs")).toBeInTheDocument()
    expect(screen.getByText("Deliver")).toBeInTheDocument()
  })

  it("renders key benefits section", () => {
    render(<IndustryFreightPage />)
    expect(screen.getByText("Key Benefits")).toBeInTheDocument()
    expect(screen.getByText("Faster Documentation")).toBeInTheDocument()
    expect(screen.getByText("Better Load Utilization")).toBeInTheDocument()
    expect(screen.getByText("Document Accuracy")).toBeInTheDocument()
    expect(screen.getByText("Less Manual Entry")).toBeInTheDocument()
  })

  it("renders screenshot placeholder", () => {
    render(<IndustryFreightPage />)
    expect(screen.getByText("See It in Action")).toBeInTheDocument()
    expect(screen.getByText("Screenshot: Freight Operations Hub")).toBeInTheDocument()
  })

  it("renders CTA banner with Start Free Trial link", () => {
    render(<IndustryFreightPage />)
    expect(screen.getByText("Ready to transform your freight operations?")).toBeInTheDocument()
    const cta = screen.getByRole("link", { name: /start free trial/i })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute("href", "/register")
  })

  it("sets correct canonical link", () => {
    render(<IndustryFreightPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/industries/freight")
  })
})
