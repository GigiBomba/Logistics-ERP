import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import IntegrationsExplorerPage from "@/pages/public/integrations-explorer"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("IntegrationsExplorerPage", () => {
  it("renders the hero section", () => {
    render(<IntegrationsExplorerPage />)
    expect(screen.getByText("Integration Explorer")).toBeInTheDocument()
  })

  it("renders the search input", () => {
    render(<IntegrationsExplorerPage />)
    expect(
      screen.getByPlaceholderText("Search integrations by name or capability...")
    ).toBeInTheDocument()
  })

  it("renders category filter buttons", () => {
    render(<IntegrationsExplorerPage />)
    expect(screen.getByText("All")).toBeInTheDocument()
    expect(screen.getByText("Telematics")).toBeInTheDocument()
    expect(screen.getByText("Accounting")).toBeInTheDocument()
    expect(screen.getByText("Communication")).toBeInTheDocument()
    expect(screen.getByText("Analytics")).toBeInTheDocument()
    expect(screen.getByText("ERP")).toBeInTheDocument()
    expect(screen.getByText("Other")).toBeInTheDocument()
  })

  it("renders integration cards", () => {
    render(<IntegrationsExplorerPage />)
    expect(screen.getByText("Geotab")).toBeInTheDocument()
    expect(screen.getByText("Samsara")).toBeInTheDocument()
    expect(screen.getByText("QuickBooks Online")).toBeInTheDocument()
    expect(screen.getByText("Xero")).toBeInTheDocument()
    expect(screen.getByText("Slack")).toBeInTheDocument()
    expect(screen.getByText("Power BI")).toBeInTheDocument()
    expect(screen.getByText("HubSpot")).toBeInTheDocument()
  })

  it("shows integration status badges", () => {
    render(<IntegrationsExplorerPage />)
    const availableBadges = screen.getAllByText("Available")
    expect(availableBadges.length).toBeGreaterThanOrEqual(1)
    const betaBadges = screen.getAllByText("Beta")
    expect(betaBadges.length).toBeGreaterThanOrEqual(1)
    const plannedBadges = screen.getAllByText("Planned")
    expect(plannedBadges.length).toBeGreaterThanOrEqual(1)
  })

  it("filters integrations by search query", () => {
    render(<IntegrationsExplorerPage />)
    const searchInput = screen.getByPlaceholderText(
      "Search integrations by name or capability..."
    )
    fireEvent.change(searchInput, { target: { value: "Slack" } })
    expect(screen.getByText("Slack")).toBeInTheDocument()
    expect(screen.queryByText("Geotab")).not.toBeInTheDocument()
  })

  it("filters integrations by category", () => {
    render(<IntegrationsExplorerPage />)
    fireEvent.click(screen.getByText("Telematics"))
    expect(screen.getByText("Geotab")).toBeInTheDocument()
    expect(screen.getByText("Samsara")).toBeInTheDocument()
    expect(screen.queryByText("Slack")).not.toBeInTheDocument()
  })

  it("expands integration card to show details", () => {
    render(<IntegrationsExplorerPage />)
    fireEvent.click(screen.getByText("Geotab"))
    expect(screen.getByText("Capabilities")).toBeInTheDocument()
    expect(screen.getByText("Setup")).toBeInTheDocument()
    expect(screen.getByText("Requirements")).toBeInTheDocument()
  })

  it("shows 'Connect' button for expanded available integrations", () => {
    render(<IntegrationsExplorerPage />)
    fireEvent.click(screen.getByText("Geotab"))
    expect(screen.getByText("Connect")).toBeInTheDocument()
  })

  it("shows 'Join Beta' badge for expanded beta integrations", () => {
    render(<IntegrationsExplorerPage />)
    fireEvent.click(screen.getByText("Samsara"))
    expect(screen.getByText("Join Beta")).toBeInTheDocument()
  })

  it("shows 'Coming Soon' badge for expanded planned integrations", () => {
    render(<IntegrationsExplorerPage />)
    fireEvent.click(screen.getByText("Xero"))
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
  })

  it("renders documentation links for expanded integrations", () => {
    render(<IntegrationsExplorerPage />)
    fireEvent.click(screen.getByText("Geotab"))
    const docLinks = screen.getAllByText("Documentation")
    expect(docLinks.length).toBeGreaterThanOrEqual(1)
  })

  it("shows no results message when no matches found", () => {
    render(<IntegrationsExplorerPage />)
    const searchInput = screen.getByPlaceholderText(
      "Search integrations by name or capability..."
    )
    fireEvent.change(searchInput, { target: { value: "xyznonexistent" } })
    expect(
      screen.getByText("No integrations match your search.")
    ).toBeInTheDocument()
    expect(screen.getByText("Clear filters")).toBeInTheDocument()
  })

  it("clear filters resets search and category", () => {
    render(<IntegrationsExplorerPage />)
    const searchInput = screen.getByPlaceholderText(
      "Search integrations by name or capability..."
    )
    fireEvent.change(searchInput, { target: { value: "xyznonexistent" } })
    fireEvent.click(screen.getByText("Clear filters"))
    expect(screen.getByText("Geotab")).toBeInTheDocument()
  })

  it("renders 'Request an integration' CTA", () => {
    render(<IntegrationsExplorerPage />)
    expect(screen.getByText("Can't find what you need?")).toBeInTheDocument()
    expect(screen.getByText("Request an integration")).toBeInTheDocument()
  })

  it("renders integration overview text for first card", () => {
    render(<IntegrationsExplorerPage />)
    expect(
      screen.getByText(/Real-time vehicle tracking, driver behavior monitoring/)
    ).toBeInTheDocument()
  })
})
