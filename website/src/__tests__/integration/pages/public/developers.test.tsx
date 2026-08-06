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
    expect(screen.getAllByText("Quick Start").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Install the toolkit")).toBeInTheDocument()
    expect(screen.getByText("Make your first request")).toBeInTheDocument()
  })

  it("shows 'Coming Soon' badges on future resources", () => {
    render(<DevelopersPage />)
    const comingSoonBadges = screen.getAllByText("Coming soon")
    expect(comingSoonBadges.length).toBe(5)
  })

  it("shows CTA section", () => {
    render(<DevelopersPage />)
    expect(screen.getAllByText("Explore the documentation").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("View docs")).toBeInTheDocument()
  })

  it("shows the Resources heading", () => {
    render(<DevelopersPage />)
    expect(screen.getByText("Resources")).toBeInTheDocument()
  })
})
