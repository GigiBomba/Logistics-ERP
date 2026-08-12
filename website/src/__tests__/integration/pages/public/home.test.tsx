import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import HomePage from "@/pages/public/home"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("HomePage", () => {
  it("renders hero section with heading and CTA buttons", () => {
    render(<HomePage />)
    expect(screen.getByText("Enterprise Logistics, Simplified")).toBeInTheDocument()
    const getStartedLinks = screen.getAllByRole("link", { name: /get started/i })
    expect(getStartedLinks.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole("link", { name: /view demo/i })).toBeInTheDocument()
  })

  it("renders statistics section", () => {
    render(<HomePage />)
    expect(screen.getByText("Core Modules")).toBeInTheDocument()
    expect(screen.getByText("Native App")).toBeInTheDocument()
    expect(screen.getByText("Online Portal")).toBeInTheDocument()
    expect(screen.getByText("Development")).toBeInTheDocument()
  })

  it("renders feature highlights", () => {
    render(<HomePage />)
    expect(screen.getByText("Profit Calculator")).toBeInTheDocument()
    // Route Planning appears both as a feature card and a screenshot label
    const routePlanningElements = screen.getAllByText("Route Planning")
    expect(routePlanningElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Dispatch Management")).toBeInTheDocument()
    expect(screen.getByText("Fleet Management")).toBeInTheDocument()
    expect(screen.getByText("Document Management")).toBeInTheDocument()
    expect(screen.getByText("Analytics & Reporting")).toBeInTheDocument()
  })

  it("renders 'See all features' link to /features", () => {
    render(<HomePage />)
    const link = screen.getByRole("link", { name: /see all features/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/features")
  })

  it("renders workflow section", () => {
    render(<HomePage />)
    expect(screen.getByText("How It Works")).toBeInTheDocument()
    expect(screen.getByText("Calculate")).toBeInTheDocument()
    expect(screen.getByText("Plan")).toBeInTheDocument()
    expect(screen.getByText("Dispatch")).toBeInTheDocument()
  })

  it("renders benefits section", () => {
    render(<HomePage />)
    expect(screen.getByText("Why Operion?")).toBeInTheDocument()
    expect(screen.getByText("Reduce Costs")).toBeInTheDocument()
    expect(screen.getByText("Increase Speed")).toBeInTheDocument()
    expect(screen.getByText("Eliminate Paperwork")).toBeInTheDocument()
    expect(screen.getByText("Scale Operations")).toBeInTheDocument()
  })

  it("renders screenshot category placeholders", () => {
    render(<HomePage />)
    // Route Planning appears both as a feature card and screenshot label
    const routePlanningElements = screen.getAllByText("Route Planning")
    expect(routePlanningElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Fleet Dashboard")).toBeInTheDocument()
    expect(screen.getByText("Dispatch Console")).toBeInTheDocument()
  })

  it("renders roadmap items", () => {
    render(<HomePage />)
    expect(screen.getByText("Vehicle Maintenance Tracking")).toBeInTheDocument()
    expect(screen.getByText("PostgreSQL Migration")).toBeInTheDocument()
    expect(screen.getByText("Mobile Companion App")).toBeInTheDocument()
  })

  it("renders FAQ section with questions", () => {
    render(<HomePage />)
    expect(screen.getByText("Frequently Asked Questions")).toBeInTheDocument()
    expect(screen.getByText("What is Operion?")).toBeInTheDocument()
    expect(screen.getByText("Is Operion free?")).toBeInTheDocument()
    expect(screen.getByText("What platforms are supported?")).toBeInTheDocument()
  })

  it("renders CTA section at the bottom", () => {
    render(<HomePage />)
    expect(screen.getByText("Ready to get started?")).toBeInTheDocument()
    expect(screen.getByText("Operion is free during active development.")).toBeInTheDocument()
  })

  it("renders hero CTA link pointing to /register", () => {
    render(<HomePage />)
    const getStartedLinks = screen.getAllByRole("link", { name: /get started/i })
    const heroCta = getStartedLinks.find((l) => l.getAttribute("href") === "/register")
    expect(heroCta).toBeInTheDocument()
    expect(heroCta).toHaveAttribute("href", "/register")
  })

  it("renders secondary CTA link pointing to /features", () => {
    render(<HomePage />)
    const secondary = screen.getByRole("link", { name: /view demo/i })
    expect(secondary).toHaveAttribute("href", "/features")
  })

  it("renders navigation links in the page", () => {
    render(<HomePage />)
    // Link to features page
    const featuresLinks = screen.getAllByRole("link", { name: /features/i })
    expect(featuresLinks.length).toBeGreaterThanOrEqual(1)
    // At least one link to /features
    const featuresHref = screen.getAllByRole("link").filter((l) => l.getAttribute("href") === "/features")
    expect(featuresHref.length).toBeGreaterThanOrEqual(1)
  })
})
