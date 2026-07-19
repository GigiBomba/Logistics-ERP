import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import AdminWaitlistPage from "@/pages/admin/waitlist/admin-waitlist"
import { useAuth } from "@/contexts/auth-provider"
import { waitlistApi } from "@/api/endpoints"
import { createMockAuthContext } from "@/test-utils"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("@/api/endpoints", () => ({
  waitlistApi: {
    getStats: vi.fn(),
  },
}))

const mockStats = {
  total: 342,
  by_status: { joined: 342, invited: 189, activated: 76, converted: 28 },
  by_country: { US: 120, DE: 65, RO: 42 },
  by_company_size: { "1-10": 150, "11-50": 100 },
  by_fleet_size: { "1-5": 180, "6-20": 90 },
  by_source: { organic: 200, referral: 80, ad: 62 },
  growth_daily: [
    { date: "2026-06-01", count: 5 },
    { date: "2026-06-02", count: 3 },
    { date: "2026-06-03", count: 8 },
  ],
  conversion_rate: 0.082,
}

const mockAdmin = createMockAuthContext({ isAdmin: true })

describe("AdminWaitlistPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(mockAdmin)
    vi.mocked(waitlistApi.getStats).mockResolvedValue({ data: mockStats })
  })

  describe("page header", () => {
    it("renders the page header title", async () => {
      render(<AdminWaitlistPage />)
      expect(await screen.findByText("Waitlist Management")).toBeInTheDocument()
    })

    it("renders the subtitle with total signup count on successful load", async () => {
      render(<AdminWaitlistPage />)
      expect(
        await screen.findByText(/342 total signups/)
      ).toBeInTheDocument()
    })

    it("sets the page title via Helmet", async () => {
      render(<AdminWaitlistPage />)
      await screen.findByText("Waitlist Management")
      expect(document.title).toBe("Waitlist Management — Operion ERP")
    })

    it("shows loading indicator in subtitle while stats load", () => {
      // Never resolve the promise so it stays in loading state
      vi.mocked(waitlistApi.getStats).mockImplementationOnce(
        () => new Promise(() => {})
      )
      render(<AdminWaitlistPage />)
      expect(screen.getByText("Loading waitlist stats…")).toBeInTheDocument()
    })
  })

  describe("access control", () => {
    it("renders access denied for non-admin users", () => {
      vi.mocked(useAuth).mockReturnValue(
        createMockAuthContext({ isAdmin: false })
      )
      render(<AdminWaitlistPage />)
      expect(screen.getByText("Access Denied")).toBeInTheDocument()
      expect(
        screen.getByText("You do not have permission to access this page.")
      ).toBeInTheDocument()
    })

    it("does not call getStats when user is not admin", () => {
      vi.mocked(useAuth).mockReturnValue(
        createMockAuthContext({ isAdmin: false })
      )
      render(<AdminWaitlistPage />)
      expect(waitlistApi.getStats).not.toHaveBeenCalled()
    })
  })

  describe("tab navigation", () => {
    it("renders all three tab triggers", async () => {
      render(<AdminWaitlistPage />)
      expect(await screen.findByRole("tab", { name: "Overview" })).toBeInTheDocument()
      expect(screen.getByRole("tab", { name: "Entries" })).toBeInTheDocument()
      expect(screen.getByRole("tab", { name: "Campaign" })).toBeInTheDocument()
    })

    it("defaults to the overview tab", async () => {
      render(<AdminWaitlistPage />)
      const overviewTab = await screen.findByRole("tab", { name: "Overview" })
      expect(overviewTab).toHaveAttribute("data-state", "active")
    })
  })

  describe("tab content rendering", () => {
    it("renders OverviewTab with stats when overview tab is active", async () => {
      render(<AdminWaitlistPage />)
      // Overview tab content — conversion rate rendering from mockStats
      expect(await screen.findByText("8.2%")).toBeInTheDocument()
      expect(screen.getByText("Conversion rate (joined → converted)")).toBeInTheDocument()
    })

    it("shows skeleton loading in overview tab while stats are loading", () => {
      vi.mocked(waitlistApi.getStats).mockImplementationOnce(
        () => new Promise(() => {})
      )
      render(<AdminWaitlistPage />)
      // Overview shows skeletons when loading and no stats yet
      const skeletons = document.querySelectorAll(".h-28")
      expect(skeletons.length).toBeGreaterThanOrEqual(4)
    })

    it("renders campaign tab content when clicked", async () => {
      render(<AdminWaitlistPage />)
      const campaignTab = await screen.findByRole("tab", { name: "Campaign" })
      campaignTab.click()
      expect(
        await screen.findByText("Campaign Sending")
      ).toBeInTheDocument()
      expect(
        screen.getByText("Mass outreach to waitlist segments")
      ).toBeInTheDocument()
    })
  })
})
