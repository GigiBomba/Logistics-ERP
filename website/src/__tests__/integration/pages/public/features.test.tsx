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
    expect(screen.getByText("Powerful Features for Modern Logistics")).toBeInTheDocument()
    expect(
      screen.getByText(
        /Everything you need to run a transport operation/i
      )
    ).toBeInTheDocument()
  })

  it("renders all 6 feature categories", () => {
    render(<FeaturesPage />)
    expect(screen.getByText("Route Planning & Optimization")).toBeInTheDocument()
    expect(screen.getByText("Fleet Management")).toBeInTheDocument()
    expect(screen.getByText("Dispatch & Operations")).toBeInTheDocument()
    expect(screen.getByText("Document Management")).toBeInTheDocument()
    expect(screen.getByText("Analytics & Reporting")).toBeInTheDocument()
    expect(screen.getByText("Driver Management")).toBeInTheDocument()
  })

  it("renders 'The Problem' badge for each category", () => {
    render(<FeaturesPage />)
    const problemBadges = screen.getAllByText("The Problem")
    expect(problemBadges).toHaveLength(6)
  })

  it("renders feature items within categories", () => {
    render(<FeaturesPage />)
    // Route Planning items
    expect(screen.getByText("Route Planning & Optimization")).toBeInTheDocument()
    // Fleet Management items
    expect(screen.getByText("Fleet Management")).toBeInTheDocument()
    // Feature item titles use fallback keys (missing from en.json)
    const featureTitles = screen.getAllByText(/features\.[a-z]+\.[a-z]+\.title/)
    // 6 categories × 3 items each = 18 feature cards
    expect(featureTitles.length).toBe(18)
  })

  it("renders screenshot placeholders for each category", () => {
    render(<FeaturesPage />)
    // Screenshot label uses fallback key (missing from en.json)
    const screenshotTexts = screen.getAllByText(/features\.screenshot/i)
    // At least 6 placeholders (one per category)
    expect(screenshotTexts.length).toBeGreaterThanOrEqual(6)
  })

  it("renders integrations text for categories that have it", () => {
    render(<FeaturesPage />)
    // Integrations label uses fallback key (missing from en.json)
    const integrationsElements = screen.getAllByText(/features\.integrations/i)
    expect(integrationsElements.length).toBeGreaterThanOrEqual(1)
  })

  it("renders FAQ section", () => {
    render(<FeaturesPage />)
    expect(screen.getByText("Feature FAQ")).toBeInTheDocument()
  })

  it("renders CTA banner at the bottom", () => {
    render(<FeaturesPage />)
    // CTA banner heading and button — both use fallback keys
    const ctaTitle = screen.getByText("features.cta.title")
    expect(ctaTitle).toBeInTheDocument()
    const ctaButton = screen.getByText("features.cta.button")
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
    expect(canonical).toHaveAttribute("href", "https://operion.com/features")
  })
})
