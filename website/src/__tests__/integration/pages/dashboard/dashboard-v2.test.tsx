import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import DashboardPage from "@/pages/dashboard/dashboard"

vi.mock("@/services/queries", () => ({
  useDevices: vi.fn(() => ({ data: [], isLoading: false })),
  useCompany: vi.fn(() => ({ data: { company_name: "Test Corp", subscription_tier: "professional", storage_used_mb: 2355, storage_limit_mb: 10240 }, isLoading: false })),
  useTickets: vi.fn(() => ({ data: [], isLoading: false })),
  useServiceStatus: vi.fn(() => ({ data: [{ titleKey: "status.components", descKey: "status.componentsDesc", services: [{ nameKey: "status.desktopApp", descKey: "status.desktopAppDesc", status: "maintenance", updatedAt: "2026-01-01" }] }], isLoading: false })),
  useAnnouncements: vi.fn(() => ({ data: [], isLoading: false })),
  useChangelog: vi.fn(() => ({ data: [], isLoading: false })),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("DashboardPage (Enhanced)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Welcome back" heading', () => {
    render(<DashboardPage />)
    expect(screen.getByText("Welcome back")).toBeInTheDocument()
  })

  it("renders dashboard sections", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Latest Version")).toBeInTheDocument()
    expect(screen.getByText("Storage Usage")).toBeInTheDocument()
  })

  it("shows tabs (Overview)", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Overview")).toBeInTheDocument()
  })

  it("shows Documentation shortcuts", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Getting Started")).toBeInTheDocument()
    expect(screen.getByText("Route Planning")).toBeInTheDocument()
    expect(screen.getByText("Dispatch")).toBeInTheDocument()
    expect(screen.getByText("Integrations")).toBeInTheDocument()
    expect(screen.getByText("API Reference")).toBeInTheDocument()
  })

  it("shows quick action cards (Downloads, Documentation, Support)", () => {
    render(<DashboardPage />)
    expect(screen.getByText("Downloads")).toBeInTheDocument()
    expect(screen.getAllByText("Documentation").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Support")).toBeInTheDocument()
  })

  it("shows version badge", () => {
    render(<DashboardPage />)
    // Version badge shows "Latest Version" from dashboard.latestVersion
    expect(screen.getByText("Latest Version")).toBeInTheDocument()
  })
})
