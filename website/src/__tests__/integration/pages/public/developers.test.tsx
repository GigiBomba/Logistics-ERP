import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@/test-utils"
import DevelopersPage from "@/pages/public/developers"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("DevelopersPage", () => {
  it("renders 'Developer Resources' heading", () => {
    render(<DevelopersPage />)
    expect(screen.getByText("Developer Resources")).toBeInTheDocument()
  })

  it("shows resource cards (Toolkit, API, SDK, etc.)", () => {
    render(<DevelopersPage />)
    expect(screen.getByText("Toolkit")).toBeInTheDocument()
    expect(screen.getByText("API Reference")).toBeInTheDocument()
    expect(screen.getByText("SDK & Libraries")).toBeInTheDocument()
    expect(screen.getByText("Integration Guides")).toBeInTheDocument()
    expect(screen.getByText("Webhooks")).toBeInTheDocument()
    expect(screen.getByText("Community")).toBeInTheDocument()
  })

  it("shows Quick Start section", () => {
    render(<DevelopersPage />)
    const quickStartEls = screen.getAllByText("Quick Start")
    expect(quickStartEls.length).toBeGreaterThanOrEqual(1)
  })

  it("shows resource badges", () => {
    render(<DevelopersPage />)
    const badgeEls = screen.getAllByText("Coming soon")
    expect(badgeEls.length).toBeGreaterThanOrEqual(1)
  })

  it("shows CTA section", () => {
    render(<DevelopersPage />)
    const ctaEls = screen.getAllByText("Explore the documentation")
    expect(ctaEls.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("View docs")).toBeInTheDocument()
  })

  it("shows the Resources heading", () => {
    render(<DevelopersPage />)
    expect(screen.getByText("Resources")).toBeInTheDocument()
  })
})
