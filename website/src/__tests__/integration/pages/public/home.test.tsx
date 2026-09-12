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
    expect(screen.getByText("The Complete Logistics Operating System, Powered by AI")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /see the ai in action/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /watch the workflow demo/i })).toBeInTheDocument()
  })

  it("renders statistics section", () => {
    render(<HomePage />)
    expect(screen.getByText("Autonomous Workflows")).toBeInTheDocument()
    expect(screen.getByText("Platform Apps")).toBeInTheDocument()
    expect(screen.getByText("Web Portal")).toBeInTheDocument()
    expect(screen.getByText("Operational")).toBeInTheDocument()
  })

  it("renders feature highlights", () => {
    render(<HomePage />)
    expect(screen.getByText("Instant Profitability Analysis")).toBeInTheDocument()
    // Route Optimization appears both as a feature card and a screenshot label
    const routeOptimizationElements = screen.getAllByText("Autonomous Route Optimization")
    expect(routeOptimizationElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("One-Instruction Dispatching")).toBeInTheDocument()
    expect(screen.getByText("Proactive Fleet Operations")).toBeInTheDocument()
    expect(screen.getByText("Automated Document Generation")).toBeInTheDocument()
    expect(screen.getByText("AI-Driven Analytics")).toBeInTheDocument()
  })

  it("renders 'Explore all capabilities' link to /features", () => {
    render(<HomePage />)
    const link = screen.getByRole("link", { name: /explore all capabilities/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/features")
  })

  it("renders workflow section", () => {
    render(<HomePage />)
    // "From Intent to Execution" appears both as the section heading and an AI step title
    const howItWorksElements = screen.getAllByText("From Intent to Execution")
    expect(howItWorksElements.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("State Your Objective")).toBeInTheDocument()
    expect(screen.getByText("AI Executes the Workflow")).toBeInTheDocument()
    expect(screen.getByText("Deliver the Result")).toBeInTheDocument()
  })

  it("renders benefits section", () => {
    render(<HomePage />)
    expect(screen.getByText("Why Transport Companies Choose Operion")).toBeInTheDocument()
    expect(screen.getByText("Fewer Empty Kilometers")).toBeInTheDocument()
    expect(screen.getByText("Faster Dispatching")).toBeInTheDocument()
    expect(screen.getByText("Zero Manual Data Entry")).toBeInTheDocument()
    expect(screen.getByText("Scale Without Adding Headcount")).toBeInTheDocument()
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
    expect(screen.getByText("Mobile Companion App")).toBeInTheDocument()
    expect(screen.getByText("Autonomous Dispatch Engine")).toBeInTheDocument()
    expect(screen.getByText("Productization & Testing")).toBeInTheDocument()
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
    expect(screen.getByText("Ready to see autonomous logistics in action?")).toBeInTheDocument()
    expect(screen.getByText(/Tell Operion what you need accomplished/i)).toBeInTheDocument()
  })

  it("renders hero CTA link pointing to /waitlist", () => {
    render(<HomePage />)
    const heroCta = screen.getByRole("link", { name: /see the ai in action/i })
    expect(heroCta).toBeInTheDocument()
    expect(heroCta).toHaveAttribute("href", "/waitlist")
  })

  it("renders secondary CTA link pointing to /features", () => {
    render(<HomePage />)
    const secondary = screen.getByRole("link", { name: /watch the workflow demo/i })
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
