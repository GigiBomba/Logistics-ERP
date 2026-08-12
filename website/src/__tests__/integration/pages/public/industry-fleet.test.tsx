import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import IndustryFleetPage from "@/pages/public/industry-fleet"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IndustryFleetPage", () => {
  it("renders page header with title", () => {
    render(<IndustryFleetPage />)
    expect(screen.getByText("Operion for Fleet Managers")).toBeInTheDocument()
  })

  it("renders challenges section with fleet-specific challenges", () => {
    render(<IndustryFleetPage />)
    expect(screen.getByText("Industry Challenges")).toBeInTheDocument()
    expect(screen.getByText("Maintenance Scheduling")).toBeInTheDocument()
    expect(screen.getByText("Driver Compliance")).toBeInTheDocument()
    expect(screen.getByText("Vehicle Tracking")).toBeInTheDocument()
    expect(screen.getByText("Cost Control")).toBeInTheDocument()
  })

  it("renders solutions section with fleet management benefits", () => {
    render(<IndustryFleetPage />)
    expect(screen.getByText("How Operion Helps")).toBeInTheDocument()
    expect(screen.getByText("Maintenance Alerts")).toBeInTheDocument()
    expect(screen.getByText("Tachograph Integration")).toBeInTheDocument()
    expect(screen.getByText("GPS Tracking")).toBeInTheDocument()
    expect(screen.getByText("Expense Analytics")).toBeInTheDocument()
  })

  it("renders workflow section", () => {
    render(<IndustryFleetPage />)
    expect(screen.getByText("Workflow Example")).toBeInTheDocument()
    expect(screen.getByText("Schedule")).toBeInTheDocument()
    expect(screen.getByText("Monitor")).toBeInTheDocument()
    expect(screen.getByText("Track")).toBeInTheDocument()
    expect(screen.getByText("Review")).toBeInTheDocument()
    expect(screen.getByText("Optimize")).toBeInTheDocument()
  })

  it("renders key benefits section with stats", () => {
    render(<IndustryFleetPage />)
    expect(screen.getByText("Key Benefits")).toBeInTheDocument()
    expect(screen.getByText("Less Downtime")).toBeInTheDocument()
    expect(screen.getByText("Compliance Rate")).toBeInTheDocument()
    expect(screen.getByText("Lower Fleet Costs")).toBeInTheDocument()
    expect(screen.getByText("Faster Repairs")).toBeInTheDocument()
  })

  it("renders screenshot placeholder", () => {
    render(<IndustryFleetPage />)
    expect(screen.getByText("See It in Action")).toBeInTheDocument()
    expect(screen.getByText("Screenshot: Fleet Health Dashboard")).toBeInTheDocument()
  })

  it("renders CTA banner with Start Free Trial link", () => {
    render(<IndustryFleetPage />)
    expect(screen.getByText("Ready to transform your fleet operations?")).toBeInTheDocument()
    const cta = screen.getByRole("link", { name: /start free trial/i })
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute("href", "/register")
  })

  it("sets correct canonical link", () => {
    render(<IndustryFleetPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operion.com/industries/fleet")
  })
})
