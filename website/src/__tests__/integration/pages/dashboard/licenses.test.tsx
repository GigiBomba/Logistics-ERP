import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import LicensesPage from "@/pages/dashboard/licenses"
import { useLicenses, useLicenseDevices } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useLicenses: vi.fn(),
  useLicenseDevices: vi.fn(),
  useRemoveLicenseDevice: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

const MOCK_LICENSES = [
  {
    id: 1,
    plan_tier: "professional",
    status: "active",
    license_key: "PROF-2026-0001",
    seats: 25,
    seats_used: 12,
    expires_at: "2026-09-30T00:00:00Z",
  },
  {
    id: 2,
    plan_tier: "starter",
    status: "trial",
    license_key: "STAR-2026-0002",
    seats: 5,
    seats_used: 3,
    expires_at: "2026-08-31T00:00:00Z",
  },
  {
    id: 3,
    plan_tier: "enterprise",
    status: "active",
    license_key: "ENT-2026-0003",
    seats: 10,
    seats_used: 10,
    expires_at: "2027-01-31T00:00:00Z",
  },
]

const MOCK_DEVICES = [
  { id: 1, name: "Workstation-BUCH-01", os: "Windows 11", last_seen: "2026-09-01T08:00:00Z" },
  { id: 2, name: "MacBook-Pro-M3", os: "macOS Sonoma", last_seen: "2026-09-02T09:00:00Z" },
  { id: 3, name: "iPhone-15-Dispatch", os: "iOS 17", last_seen: "2026-09-03T10:00:00Z" },
  { id: 4, name: "Workstation-BER-01", os: "Windows 11", last_seen: "2026-09-04T11:00:00Z" },
  { id: 5, name: "Server-BUCH-01", os: "Ubuntu 24.04", last_seen: "2026-09-05T12:00:00Z" },
]

describe("LicensesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useLicenses).mockReturnValue({
      data: MOCK_LICENSES,
      isLoading: false,
      isError: false,
    } as any)
    vi.mocked(useLicenseDevices).mockReturnValue({
      data: MOCK_DEVICES,
      isLoading: false,
      isError: false,
    } as any)
  })

  it('renders "Licenses" heading and description', () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Licenses")).toBeInTheDocument()
    expect(screen.getByText(/Manage your Operion licenses and devices/i)).toBeInTheDocument()
  })

  it("shows Add License button", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Add License")).toBeInTheDocument()
  })

  it("shows stats cards with Total Seats, Active Seats, Available Seats", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Total Seats")).toBeInTheDocument()
    expect(screen.getByText("Active Seats")).toBeInTheDocument()
    expect(screen.getByText("Available Seats")).toBeInTheDocument()
    expect(screen.getByText("Next Renewal")).toBeInTheDocument()
  })

  it("shows correct seat counts in stats", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    // Total: 25+5+10 = 40, Active: 12+3+10 = 25, Available: 40-25 = 15
    expect(screen.getByText("40")).toBeInTheDocument()
    expect(screen.getByText("25")).toBeInTheDocument()
    expect(screen.getByText("15")).toBeInTheDocument()
  })

  it("renders all 3 license cards", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Professional")).toBeInTheDocument()
    expect(screen.getByText("Starter")).toBeInTheDocument()
    expect(screen.getByText("Enterprise")).toBeInTheDocument()
  })

  it("shows license status badges", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    const activeBadges = screen.getAllByText("active")
    expect(activeBadges.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("trial")).toBeInTheDocument()
  })

  it("shows seats used progress on license cards", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("12 / 25")).toBeInTheDocument()
    expect(screen.getByText("3 / 5")).toBeInTheDocument()
    expect(screen.getByText("10 / 10")).toBeInTheDocument()
  })

  it("shows Manage Devices links on each license card", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    const manageLinks = screen.getAllByText(/Manage Devices/i)
    expect(manageLinks.length).toBe(3)
  })

  it("shows Devices section with Active Devices tab", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Devices")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /active devices/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /device history/i })).toBeInTheDocument()
  })

  it("renders active device cards with names and platforms", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Workstation-BUCH-01")).toBeInTheDocument()
    // "Windows 11" appears on both the main page and device card
    expect(screen.getAllByText("Windows 11").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("MacBook-Pro-M3")).toBeInTheDocument()
    expect(screen.getByText("macOS Sonoma")).toBeInTheDocument()
    expect(screen.getByText("iPhone-15-Dispatch")).toBeInTheDocument()
    expect(screen.getByText("iOS 17")).toBeInTheDocument()
  })

  it("shows Active badge on device cards", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    const activeDeviceBadges = screen.getAllByText("Active")
    expect(activeDeviceBadges.length).toBeGreaterThanOrEqual(5)
  })

  it("shows Device History tab with empty state", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    fireEvent.click(screen.getByRole("tab", { name: /device history/i }))
    expect(screen.getByText(/Device history coming soon/i)).toBeInTheDocument()
  })

  it("shows Offline Activation callout", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Offline Activation")).toBeInTheDocument()
    expect(screen.getByText(/air-gapped environments/i)).toBeInTheDocument()
  })

  it("shows Floating Licenses callout", () => {
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    expect(screen.getByText("Floating Licenses")).toBeInTheDocument()
    expect(screen.getByText(/Q4 2026/i)).toBeInTheDocument()
  })

  it("shows loading spinner when isLoading is true", () => {
    vi.mocked(useLicenses).mockReturnValue({
      data: null,
      isLoading: true,
    } as any)
    render(<LicensesPage />, { initialEntries: ["/dashboard/licenses?license=1"] })
    const spinner = document.querySelector(".animate-spin")
    expect(spinner).toBeInTheDocument()
  })
})
