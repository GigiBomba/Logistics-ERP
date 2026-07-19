import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IndustryConstructionPage from "@/pages/public/industry-construction"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IndustryConstructionPage", () => {
  it("renders page header with title", () => {
    render(<IndustryConstructionPage />)
    expect(screen.getByText("Operion for Construction Logistics")).toBeInTheDocument()
  })

  it("renders challenges section with construction-specific challenges", () => {
    render(<IndustryConstructionPage />)
    expect(screen.getByText("Industry Challenges")).toBeInTheDocument()
    expect(screen.getByText("Material Delivery")).toBeInTheDocument()
    expect(screen.getByText("Site Coordination")).toBeInTheDocument()
    expect(screen.getByText("Heavy Equipment")).toBeInTheDocument()
    expect(screen.getByText("Multiple Suppliers")).toBeInTheDocument()
  })

  it("renders solutions section", () => {
    render(<IndustryConstructionPage />)
    expect(screen.getByText("How Operion Helps")).toBeInTheDocument()
    expect(screen.getByText("Material Tracking")).toBeInTheDocument()
    expect(screen.getByText("Site Scheduling")).toBeInTheDocument()
    expect(screen.getByText("Equipment Logistics")).toBeInTheDocument()
    expect(screen.getByText("Supplier Coordination")).toBeInTheDocument()
  })

  it("renders workflow section", () => {
    render(<IndustryConstructionPage />)
    expect(screen.getByText("Workflow Example")).toBeInTheDocument()
    expect(screen.getByText("Order Materials")).toBeInTheDocument()
    expect(screen.getByText("Schedule Delivery")).toBeInTheDocument()
    expect(screen.getByText("Track Equipment")).toBeInTheDocument()
    expect(screen.getByText("Site Receive")).toBeInTheDocument()
    expect(screen.getByText("Invoice")).toBeInTheDocument()
  })

  it("renders key benefits section with stats", () => {
    render(<IndustryConstructionPage />)
    expect(screen.getByText("Key Benefits")).toBeInTheDocument()
    expect(screen.getByText("Fewer Delays")).toBeInTheDocument()
    expect(screen.getByText("Lower Transport Costs")).toBeInTheDocument()
    expect(screen.getByText("Site Accuracy")).toBeInTheDocument()
    expect(screen.getByText("Faster Billing")).toBeInTheDocument()
  })

  it("renders screenshot placeholder", () => {
    render(<IndustryConstructionPage />)
    expect(screen.getByText("See It in Action")).toBeInTheDocument()
    expect(screen.getByText("Screenshot: Construction Logistics Board")).toBeInTheDocument()
  })

  it("renders CTA banner with Start Free Trial link", () => {
    render(<IndustryConstructionPage />)
    expect(screen.getByText("Ready to transform your construction logistics?")).toBeInTheDocument()
    const cta = screen.getByRole("link", { name: /start free trial/i })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute("href", "/register")
  })

  it("sets correct canonical link", () => {
    render(<IndustryConstructionPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/industries/construction")
  })
})
