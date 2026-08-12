import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IndustryManufacturingPage from "@/pages/public/industry-manufacturing"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IndustryManufacturingPage", () => {
  it("renders page header with title", () => {
    render(<IndustryManufacturingPage />)
    expect(screen.getByText("Operion for Manufacturing Logistics")).toBeInTheDocument()
  })

  it("renders challenges section with manufacturing-specific challenges", () => {
    render(<IndustryManufacturingPage />)
    expect(screen.getByText("Industry Challenges")).toBeInTheDocument()
    const supplyChainVisibility = screen.getAllByText("Supply Chain Visibility")
    expect(supplyChainVisibility.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Inventory Management")).toBeInTheDocument()
    expect(screen.getByText("Just-in-Time Delivery")).toBeInTheDocument()
    expect(screen.getByText("Multi-Facility Coordination")).toBeInTheDocument()
  })

  it("renders solutions section with manufacturing solutions", () => {
    render(<IndustryManufacturingPage />)
    expect(screen.getByText("How Operion Helps")).toBeInTheDocument()
    const supplyChainVisibility = screen.getAllByText("Supply Chain Visibility")
    expect(supplyChainVisibility.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Inventory Integration")).toBeInTheDocument()
    expect(screen.getByText("JIT Routing")).toBeInTheDocument()
    expect(screen.getByText("Multi-Site Management")).toBeInTheDocument()
  })

  it("renders workflow section", () => {
    render(<IndustryManufacturingPage />)
    expect(screen.getByText("Workflow Example")).toBeInTheDocument()
    expect(screen.getByText("Demand Signal")).toBeInTheDocument()
    expect(screen.getByText("Inventory Check")).toBeInTheDocument()
    expect(screen.getByText("Route Optimize")).toBeInTheDocument()
    expect(screen.getByText("JIT Delivery")).toBeInTheDocument()
    expect(screen.getByText("Production Line")).toBeInTheDocument()
  })

  it("renders key benefits section", () => {
    render(<IndustryManufacturingPage />)
    expect(screen.getByText("Key Benefits")).toBeInTheDocument()
    expect(screen.getByText("Inventory Reduction")).toBeInTheDocument()
    expect(screen.getByText("Faster Throughput")).toBeInTheDocument()
    expect(screen.getByText("On-Time Delivery")).toBeInTheDocument()
    expect(screen.getByText("Less Waste")).toBeInTheDocument()
  })

  it("renders screenshot placeholder", () => {
    render(<IndustryManufacturingPage />)
    expect(screen.getByText("See It in Action")).toBeInTheDocument()
    expect(screen.getByText("Screenshot: Manufacturing Supply Dashboard")).toBeInTheDocument()
  })

  it("renders CTA banner with Start Free Trial link", () => {
    render(<IndustryManufacturingPage />)
    expect(screen.getByText("Ready to transform your manufacturing operations?")).toBeInTheDocument()
    const cta = screen.getByRole("link", { name: /start free trial/i })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute("href", "/register")
  })

  it("sets correct canonical link", () => {
    render(<IndustryManufacturingPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/industries/manufacturing")
  })
})
