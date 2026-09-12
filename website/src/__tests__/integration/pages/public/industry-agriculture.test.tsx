import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IndustryAgriculturePage from "@/pages/public/industry-agriculture"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IndustryAgriculturePage", () => {
  it("renders page header with title", () => {
    render(<IndustryAgriculturePage />)
    expect(screen.getByText("Operion for Agriculture Logistics")).toBeInTheDocument()
  })

  it("renders challenges section with industry-specific challenges", () => {
    render(<IndustryAgriculturePage />)
    expect(screen.getByText("Industry Challenges")).toBeInTheDocument()
    expect(screen.getByText("Seasonal Peaks")).toBeInTheDocument()
    expect(screen.getByText("Perishable Goods")).toBeInTheDocument()
    // "Rural Routes" appears as a challenge title and in the seasonal calendar visual
    const ruralRoutes = screen.getAllByText("Rural Routes")
    expect(ruralRoutes.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Equipment Tracking")).toBeInTheDocument()
  })

  it("renders solutions section", () => {
    render(<IndustryAgriculturePage />)
    expect(screen.getByText("How Operion Helps")).toBeInTheDocument()
    expect(screen.getByText("Seasonal Scaling")).toBeInTheDocument()
    expect(screen.getByText("Temperature Monitoring")).toBeInTheDocument()
    expect(screen.getByText("Rural Route Optimization")).toBeInTheDocument()
    expect(screen.getByText("Equipment Management")).toBeInTheDocument()
  })

  it("renders workflow section", () => {
    render(<IndustryAgriculturePage />)
    expect(screen.getByText("Workflow Example")).toBeInTheDocument()
    expect(screen.getByText("Harvest Schedule")).toBeInTheDocument()
    expect(screen.getByText("Route Plan")).toBeInTheDocument()
    expect(screen.getByText("Monitor Temp")).toBeInTheDocument()
    // "Delivery" appears as a workflow step and in the seasonal calendar visual
    const deliverySteps = screen.getAllByText("Delivery")
    expect(deliverySteps.length).toBeGreaterThanOrEqual(1)
    const traceabilityWorkflow = screen.getAllByText("Traceability")
    expect(traceabilityWorkflow.length).toBeGreaterThanOrEqual(1)
  })

  it("renders key benefits section with stats", () => {
    render(<IndustryAgriculturePage />)
    expect(screen.getByText("Key Benefits")).toBeInTheDocument()
    expect(screen.getByText("Less Spoilage")).toBeInTheDocument()
    expect(screen.getByText("Faster Harvest Delivery")).toBeInTheDocument()
    expect(screen.getByText("Fuel Savings")).toBeInTheDocument()
    const traceability = screen.getAllByText("Traceability")
    expect(traceability.length).toBeGreaterThanOrEqual(1)
  })

  it("renders screenshot placeholder", () => {
    render(<IndustryAgriculturePage />)
    expect(screen.getByText("See It in Action")).toBeInTheDocument()
    expect(screen.getByText("Seasonal Logistics Calendar")).toBeInTheDocument()
  })

  it("renders CTA banner with Start Free Trial link", () => {
    render(<IndustryAgriculturePage />)
    expect(screen.getByText("Ready to transform your agriculture operations?")).toBeInTheDocument()
    const cta = screen.getByRole("link", { name: /start free trial/i })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute("href", "/register")
  })

  it("sets correct canonical link", () => {
    render(<IndustryAgriculturePage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operionerp.xyz/industries/agriculture")
  })
})
