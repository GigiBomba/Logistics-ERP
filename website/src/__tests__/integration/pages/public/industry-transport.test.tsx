import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IndustryTransportPage from "@/pages/public/industry-transport"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IndustryTransportPage", () => {
  it("renders page header with title", () => {
    render(<IndustryTransportPage />)
    expect(screen.getByText("Operion for Transport Companies")).toBeInTheDocument()
  })

  it("renders challenges section with transport-specific challenges", () => {
    render(<IndustryTransportPage />)
    expect(screen.getByText("Industry Challenges")).toBeInTheDocument()
    expect(screen.getByText("Route Inefficiency")).toBeInTheDocument()
    expect(screen.getByText("Driver Management")).toBeInTheDocument()
    expect(screen.getByText("Rising Fuel Costs")).toBeInTheDocument()
    expect(screen.getByText("Delivery Tracking")).toBeInTheDocument()
  })

  it("renders solutions section with transport features", () => {
    render(<IndustryTransportPage />)
    expect(screen.getByText("How Operion Helps")).toBeInTheDocument()
    expect(screen.getByText("AI-Powered Routing")).toBeInTheDocument()
    expect(screen.getByText("Fleet GPS Tracking")).toBeInTheDocument()
    expect(screen.getByText("Fuel Analytics")).toBeInTheDocument()
    expect(screen.getByText("Real-Time ETAs")).toBeInTheDocument()
  })

  it("renders workflow section", () => {
    render(<IndustryTransportPage />)
    expect(screen.getByText("Workflow Example")).toBeInTheDocument()
    expect(screen.getByText("Plan Route")).toBeInTheDocument()
    expect(screen.getByText("Assign Driver")).toBeInTheDocument()
    expect(screen.getByText("Track Live")).toBeInTheDocument()
    expect(screen.getByText("Deliver")).toBeInTheDocument()
    expect(screen.getByText("Analyze")).toBeInTheDocument()
  })

  it("renders key benefits section with stats", () => {
    render(<IndustryTransportPage />)
    expect(screen.getByText("Key Benefits")).toBeInTheDocument()
    expect(screen.getByText("Fuel Cost Reduction")).toBeInTheDocument()
    expect(screen.getByText("More Deliveries/Day")).toBeInTheDocument()
    expect(screen.getByText("On-Time Delivery Rate")).toBeInTheDocument()
    expect(screen.getByText("Less Admin Time")).toBeInTheDocument()
  })

  it("renders screenshot placeholder", () => {
    render(<IndustryTransportPage />)
    expect(screen.getByText("See It in Action")).toBeInTheDocument()
    expect(screen.getByText("Screenshot: Transport Dispatch Dashboard")).toBeInTheDocument()
  })

  it("renders CTA banner with Start Free Trial link", () => {
    render(<IndustryTransportPage />)
    expect(screen.getByText("Ready to transform your transport operations?")).toBeInTheDocument()
    const cta = screen.getByRole("link", { name: /start free trial/i })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute("href", "/register")
  })

  it("sets correct canonical link", () => {
    render(<IndustryTransportPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/industries/transport")
  })
})
