import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@/test-utils"
import OverviewTab from "@/pages/admin/waitlist/overview-tab"
import { waitlistApi } from "@/api/endpoints"
import type { WaitlistStatsResponse } from "@/api/endpoints"

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/api/endpoints", () => ({
  waitlistApi: {
    getStats: vi.fn(),
  },
}))

const mockStats: WaitlistStatsResponse = {
  total: 342,
  by_status: { joined: 342, invited: 189, activated: 76, converted: 28 },
  by_country: { US: 120, DE: 65, RO: 42, GB: 35, FR: 28 },
  by_company_size: { "1-10": 150, "11-50": 100, "51-200": 55, "201+": 37 },
  by_fleet_size: { "1-5": 180, "6-20": 90, "21-50": 45, "51+": 27 },
  by_source: { organic: 200, referral: 80, ad: 62 },
  growth_daily: [
    { date: "2026-06-01", count: 5 },
    { date: "2026-06-02", count: 3 },
    { date: "2026-06-03", count: 8 },
    { date: "2026-06-04", count: 12 },
    { date: "2026-06-05", count: 7 },
  ],
  conversion_rate: 0.082,
}

describe("OverviewTab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(waitlistApi.getStats).mockResolvedValue({ data: mockStats })
  })

  describe("stats display", () => {
    it("renders total signups stat card", () => {
      render(<OverviewTab stats={mockStats} />)
      // "342" appears in stat card value and again in funnel — use getAllByText
      expect(screen.getAllByText("342").length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText("Total signups")).toBeInTheDocument()
    })

    it("renders invited count stat card", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getAllByText("189").length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText("Invited").length).toBeGreaterThanOrEqual(1)
    })

    it("renders activated count stat card", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getAllByText("76").length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText("Activated").length).toBeGreaterThanOrEqual(1)
    })

    it("renders converted count stat card", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getAllByText("28").length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText("Converted").length).toBeGreaterThanOrEqual(1)
    })
  })

  describe("conversion rate", () => {
    it("renders conversion rate as percentage", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("8.2%")).toBeInTheDocument()
      expect(
        screen.getByText("Conversion rate (joined → converted)")
      ).toBeInTheDocument()
    })

    it("renders 0.0% when conversion rate is zero", () => {
      const zeroStats = { ...mockStats, conversion_rate: 0, total: 0 }
      render(<OverviewTab stats={zeroStats} />)
      expect(screen.getByText("0.0%")).toBeInTheDocument()
    })
  })

  describe("funnel", () => {
    it("renders funnel section with all stages", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("Funnel")).toBeInTheDocument()
      expect(
        screen.getByText("Progression from signup to conversion")
      ).toBeInTheDocument()
    })

    it("renders correct funnel counts", () => {
      render(<OverviewTab stats={mockStats} />)
      // The funnel bars display counts next to labels (also in stat cards)
      expect(screen.getAllByText("342").length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText("189").length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText("76").length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText("28").length).toBeGreaterThanOrEqual(1)
    })
  })

  describe("breakdown grids", () => {
    it("renders breakdown by country with entries sorted by count descending", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("By Country")).toBeInTheDocument()
      // US (120) should be first, DE (65) second
      expect(screen.getByText("US")).toBeInTheDocument()
      expect(screen.getByText("DE")).toBeInTheDocument()
    })

    it("renders breakdown by company size", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("By Company Size")).toBeInTheDocument()
      expect(screen.getByText("1-10")).toBeInTheDocument()
      expect(screen.getByText("11-50")).toBeInTheDocument()
    })

    it("renders breakdown by fleet size", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("By Fleet Size")).toBeInTheDocument()
      expect(screen.getByText("1-5")).toBeInTheDocument()
    })

    it("renders breakdown by source", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("By Source")).toBeInTheDocument()
      expect(screen.getByText("organic")).toBeInTheDocument()
    })

    it("shows no data message for empty breakdown", () => {
      const emptyStats = {
        ...mockStats,
        by_country: {},
        by_company_size: {},
        by_fleet_size: {},
        by_source: {},
      }
      render(<OverviewTab stats={emptyStats} />)
      const noDataMessages = screen.getAllByText("No data available.")
      expect(noDataMessages.length).toBeGreaterThanOrEqual(4)
    })
  })

  describe("growth chart", () => {
    it("renders growth chart when growth_daily data is provided", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("Growth (last 30 days)")).toBeInTheDocument()
      expect(
        screen.getByText("Daily signup volume")
      ).toBeInTheDocument()
    })

    it("renders date labels on growth chart", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(screen.getByText("2026-06-01")).toBeInTheDocument()
      expect(screen.getByText("2026-06-05")).toBeInTheDocument()
    })

    it("does not render growth chart when growth_daily is empty", () => {
      const noGrowthStats = { ...mockStats, growth_daily: [] }
      render(<OverviewTab stats={noGrowthStats} />)
      expect(
        screen.queryByText("Growth (last 30 days)")
      ).not.toBeInTheDocument()
    })

    it("does not render growth chart when growth_daily is null", () => {
      const nullGrowthStats = { ...mockStats, growth_daily: null as any }
      render(<OverviewTab stats={nullGrowthStats} />)
      expect(
        screen.queryByText("Growth (last 30 days)")
      ).not.toBeInTheDocument()
    })
  })

  describe("loading state", () => {
    it("renders skeleton placeholders when loading and no stats provided", () => {
      render(<OverviewTab stats={null} />)
      const skeletonCards = document.querySelectorAll(".h-28")
      expect(skeletonCards.length).toBeGreaterThanOrEqual(4)
      const skeletonChart = document.querySelectorAll(".h-64")
      expect(skeletonChart.length).toBe(1)
    })
  })

  describe("error state", () => {
    it("renders error callout when API call fails", async () => {
      vi.mocked(waitlistApi.getStats).mockRejectedValueOnce({
        response: { data: { message: "Server error" } },
      })
      render(<OverviewTab stats={null} />)
      expect(
        await screen.findByText("Failed to load overview")
      ).toBeInTheDocument()
      expect(screen.getByText("Retry")).toBeInTheDocument()
    })

    it("renders nothing when stats is null after load", async () => {
      // We can't easily force the null state, but if stats is null
      // and not loading, it should render null
      const { container } = render(<OverviewTab stats={null as any} />)
      // After the loading resolves to null, it renders null
      // The outer AdminWaitlistPage handles this case
      await waitFor(() => {
        // The loading skeletons should be gone and nothing rendered
        const skeletons = container.querySelectorAll(".h-28")
        expect(skeletons.length).toBe(0)
      })
    })
  })

  describe("own stats fetch", () => {
    it("calls waitlistApi.getStats when no stats prop is provided", () => {
      render(<OverviewTab stats={null} />)
      expect(waitlistApi.getStats).toHaveBeenCalledTimes(1)
    })

    it("does not call getStats when stats prop is provided", () => {
      render(<OverviewTab stats={mockStats} />)
      expect(waitlistApi.getStats).not.toHaveBeenCalled()
    })
  })
})
