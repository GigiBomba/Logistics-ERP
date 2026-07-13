import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import DashboardPage from "@/pages/dashboard/dashboard"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("DashboardPage (Enhanced)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Welcome back" heading', () => {
    render(<DashboardPage />)
    expect(screen.getByText("Welcome back")).toBeInTheDocument()
  })

  it("renders stats cards (Licenses, Team, Sessions, Storage)", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Active Licenses")).toBeInTheDocument()
    expect(screen.getByText("Team Members")).toBeInTheDocument()
    // "Active Sessions" appears both as a stat label and a card title
    expect(screen.getAllByText("Active Sessions").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Storage Used")).toBeInTheDocument()
  })

  it("shows tabs (Overview / Activity)", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Overview")).toBeInTheDocument()
    expect(screen.getByText("Activity")).toBeInTheDocument()
  })

  it("shows Documentation shortcuts", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Getting Started")).toBeInTheDocument()
    expect(screen.getByText("Route Planning")).toBeInTheDocument()
    expect(screen.getByText("Dispatch")).toBeInTheDocument()
    expect(screen.getByText("Integrations")).toBeInTheDocument()
    expect(screen.getByText("API Reference")).toBeInTheDocument()
  })

  it("shows Storage usage card with progress", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Storage Usage")).toBeInTheDocument()
    expect(screen.getByText("2.3 GB / 10 GB")).toBeInTheDocument()
  })

  it("shows Latest Release section", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Latest Release")).toBeInTheDocument()
  })

  it("shows quick action cards (Downloads, Documentation, Support)", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Downloads")).toBeInTheDocument()
    // "Documentation" appears as both a section heading and a shortcut label
    expect(screen.getAllByText("Documentation").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Support")).toBeInTheDocument()
  })

  it("shows announcements", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Announcements")).toBeInTheDocument()
    expect(screen.getByText(/Operion 1.0 launching/i)).toBeInTheDocument()
    expect(screen.getByText(/New documentation center now live/i)).toBeInTheDocument()
  })

  it("shows subscription summary card", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Subscription")).toBeInTheDocument()
    expect(screen.getByText("Professional Plan")).toBeInTheDocument()
  })

  it("shows license usage card", () => {
    render(<DashboardPage />)
    expect(screen.getByText("5 / 25 Licenses Used")).toBeInTheDocument()
  })

  it("shows active sessions card with session count", () => {
    render(<DashboardPage />)
    expect(screen.getByText("3 active sessions")).toBeInTheDocument()
    expect(screen.getByText("Manage Sessions")).toBeInTheDocument()
  })

  it("shows Quick Actions heading", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Quick Actions")).toBeInTheDocument()
  })

  it("shows recent activity when clicking Activity tab", () => {
    render(<DashboardPage />)
    const activityTab = screen.getByRole("tab", { name: /activity/i })
    fireEvent.click(activityTab)
    expect(screen.getByText("Recent Activity")).toBeInTheDocument()
  })
})
