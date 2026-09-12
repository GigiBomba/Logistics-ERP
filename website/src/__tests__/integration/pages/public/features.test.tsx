import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import FeaturesPage from "@/pages/public/features"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("FeaturesPage", () => {
  it("renders page header", () => {
    render(<FeaturesPage />)
    expect(screen.getByText("Autonomous Logistics Workflows, Not Feature Lists")).toBeInTheDocument()
    expect(
      screen.getByText(
        /Operion is not a collection of modules/i
      )
    ).toBeInTheDocument()
  })

  it("renders all 7 feature categories", () => {
    render(<FeaturesPage />)
    expect(screen.getByText("Intelligent Route Execution")).toBeInTheDocument()
    expect(screen.getByText("Autonomous Fleet Operations")).toBeInTheDocument()
    expect(screen.getByText("One-Instruction Dispatching")).toBeInTheDocument()
    expect(screen.getByText("Automated Document Workflows")).toBeInTheDocument()
    expect(screen.getByText("Self-Updating Analytics")).toBeInTheDocument()
    expect(screen.getByText("Automated Driver Coordination")).toBeInTheDocument()
    expect(screen.getByText("ARGO — AI Logistics Agent")).toBeInTheDocument()
  })

  it("renders 'The Problem' badge for each category", () => {
    render(<FeaturesPage />)
    const problemBadges = screen.getAllByText("Before Operion")
    expect(problemBadges).toHaveLength(7)
  })

  it("renders feature items within categories", () => {
    render(<FeaturesPage />)
    // Route Planning items
    expect(screen.getByText("Multi-Stop Optimization")).toBeInTheDocument()
    // Fleet Management items
    expect(screen.getByText("Live Fleet Visibility")).toBeInTheDocument()
    // Dispatch items
    expect(screen.getByText("AI-Powered Job Assignment")).toBeInTheDocument()
    // AI items
    expect(screen.getByText("ARGO AI Logistics Agent")).toBeInTheDocument()
    // Document items
    expect(screen.getByText("Intelligent Document Processing")).toBeInTheDocument()
    // Analytics items
    expect(screen.getByText("Live KPI Dashboards")).toBeInTheDocument()
    // Driver items
    expect(screen.getByText("Automated Driver Records")).toBeInTheDocument()
  })

  it("renders screenshot placeholders for each category", () => {
    render(<FeaturesPage />)
    // Each category renders a browser-chrome placeholder (7 total)
    const screenshotTexts = screen.getAllByText(/app\.operionerp\.xyz\//)
    expect(screenshotTexts).toHaveLength(7)
  })

  it("renders integrations text for categories that have it", () => {
    render(<FeaturesPage />)
    // One integrations line per category (7 total)
    const integrationsElements = screen.getAllByText(/ARGO connects to your existing freight exchanges/i)
    expect(integrationsElements).toHaveLength(7)
  })

  it("renders FAQ section", () => {
    render(<FeaturesPage />)
    expect(screen.getByText("Autonomous Workflow FAQ")).toBeInTheDocument()
  })

  it("renders CTA banner at the bottom", () => {
    render(<FeaturesPage />)
    const ctaTitle = screen.getByText("Ready to dispatch with a single instruction?")
    expect(ctaTitle).toBeInTheDocument()
    const ctaButton = screen.getByText("Try Autonomous Dispatching")
    expect(ctaButton).toBeInTheDocument()
  })

  it("renders a link to /register in CTA", () => {
    render(<FeaturesPage />)
    const registerLinks = screen
      .getAllByRole("link")
      .filter((l) => l.getAttribute("href") === "/register")
    expect(registerLinks.length).toBeGreaterThanOrEqual(1)
  })

  it("renders canonical link in helmet", () => {
    render(<FeaturesPage />)
    const canonical = document.querySelector('link[rel="canonical"]')
    expect(canonical).toBeInTheDocument()
    expect(canonical).toHaveAttribute("href", "https://operionerp.xyz/features")
  })
})
