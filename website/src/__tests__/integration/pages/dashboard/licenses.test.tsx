import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import LicensesPage from "@/pages/dashboard/licenses"
import { useLicenses } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useLicenses: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("LicensesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useLicenses).mockReturnValue({
      data: null,
      isLoading: false,
    } as any)
  })

  it('renders "Licenses" heading and description', () => {
    render(<LicensesPage />)
    expect(screen.getByText("Licenses")).toBeInTheDocument()
    expect(screen.getByText(/Manage your Operion licenses and devices/i)).toBeInTheDocument()
  })

  it("shows Add License button", () => {
    render(<LicensesPage />)
    expect(screen.getByText("Add License")).toBeInTheDocument()
  })

  it("shows stats cards with Total Seats, Active Seats, Available Seats", () => {
    render(<LicensesPage />)
    expect(screen.getByText("Total Seats")).toBeInTheDocument()
    expect(screen.getByText("Active Seats")).toBeInTheDocument()
    expect(screen.getByText("Available Seats")).toBeInTheDocument()
    expect(screen.getByText("Next Renewal")).toBeInTheDocument()
  })

  it("shows correct seat counts in stats", () => {
    render(<LicensesPage />)
    // Total: 25+5+10 = 40, Active: 12+3+10 = 25, Available: 40-25 = 15
    expect(screen.getByText("40")).toBeInTheDocument()
    expect(screen.getByText("25")).toBeInTheDocument()
    expect(screen.getByText("15")).toBeInTheDocument()
  })

  it("renders all 3 license cards", () => {
    render(<LicensesPage />)
    expect(screen.getByText("Professional")).toBeInTheDocument()
    expect(screen.getByText("Starter")).toBeInTheDocument()
    expect(screen.getByText("Enterprise")).toBeInTheDocument()
  })

  it("shows license status badges", () => {
    render(<LicensesPage />)
    const activeBadges = screen.getAllByText("active")
    expect(activeBadges.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("trial")).toBeInTheDocument()
  })

  it("shows seats used progress on license cards", () => {
    render(<LicensesPage />)
    expect(screen.getByText("12 / 25")).toBeInTheDocument()
    expect(screen.getByText("3 / 5")).toBeInTheDocument()
    expect(screen.getByText("10 / 10")).toBeInTheDocument()
  })

  it("shows Manage Devices links on each license card", () => {
    render(<LicensesPage />)
    const manageLinks = screen.getAllByText(/Manage Devices/i)
    expect(manageLinks.length).toBe(3)
  })

  it("shows Devices section with Active Devices tab", () => {
    render(<LicensesPage />)
    expect(screen.getByText("Devices")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /active devices/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /device history/i })).toBeInTheDocument()
  })

  it("renders active device cards with names and platforms", () => {
    render(<LicensesPage />)
    expect(screen.getByText("Workstation-BUCH-01")).toBeInTheDocument()
    // "Windows 11" appears on both the main page and device card
    expect(screen.getAllByText("Windows 11").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("MacBook-Pro-M3")).toBeInTheDocument()
    expect(screen.getByText("macOS Sonoma")).toBeInTheDocument()
    expect(screen.getByText("iPhone-15-Dispatch")).toBeInTheDocument()
    expect(screen.getByText("iOS 17")).toBeInTheDocument()
  })

  it("shows Active badge on device cards", () => {
    render(<LicensesPage />)
    const activeDeviceBadges = screen.getAllByText("Active")
    expect(activeDeviceBadges.length).toBeGreaterThanOrEqual(5)
  })

  it("shows Device History tab with empty state", () => {
    render(<LicensesPage />)
    fireEvent.click(screen.getByRole("tab", { name: /device history/i }))
    expect(screen.getByText(/Device history coming soon/i)).toBeInTheDocument()
  })

  it("shows Offline Activation callout", () => {
    render(<LicensesPage />)
    expect(screen.getByText("Offline Activation")).toBeInTheDocument()
    expect(screen.getByText(/air-gapped environments/i)).toBeInTheDocument()
  })

  it("shows Floating Licenses callout", () => {
    render(<LicensesPage />)
    expect(screen.getByText("Floating Licenses")).toBeInTheDocument()
    expect(screen.getByText(/Q4 2026/i)).toBeInTheDocument()
  })

  it("shows loading spinner when isLoading is true", () => {
    vi.mocked(useLicenses).mockReturnValue({
      data: null,
      isLoading: true,
    } as any)
    render(<LicensesPage />)
    const spinner = document.querySelector(".animate-spin")
    expect(spinner).toBeInTheDocument()
  })
})
