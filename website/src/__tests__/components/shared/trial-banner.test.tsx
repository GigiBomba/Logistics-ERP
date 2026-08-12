import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { TrialBanner } from "@/components/shared/trial-banner"
import { useSubscription } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useSubscription: vi.fn(),
}))

const mockSubscription = (overrides: Record<string, unknown> = {}) => ({
  status: "trialing",
  licensed_truck_count: 3,
  price_per_truck_erp_cents: 9900,
  price_per_truck_ai_cents: 4900,
  ai_copilot_enabled: false,
  priority_support_enabled: false,
  priority_support_price_cents: 0,
  api_access_enabled: false,
  api_access_price_cents: 0,
  billing_term: "monthly",
  annual_discount_pct: 0,
  service_credit_cents: 0,
  current_period_end: "2026-09-01T00:00:00Z",
  trial_ends_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
  payment_deferred_until: null,
  pending_truck_count: null,
  ...overrides,
})

describe("TrialBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it("renders when trial is active", () => {
    vi.mocked(useSubscription).mockReturnValue({ data: mockSubscription() } as any)
    render(<TrialBanner />)
    expect(screen.getByText(/Free trial active/)).toBeInTheDocument()
  })

  it("renders urgent styling when expiring within 4 days", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: mockSubscription({
        trial_ends_at: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
      }),
    } as any)
    render(<TrialBanner />)
    expect(screen.getByText(/trial ends in/i)).toBeInTheDocument()
  })

  it("is hidden when trial has expired", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: mockSubscription({
        status: "active",
        trial_ends_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      }),
    } as any)
    render(<TrialBanner />)
    expect(screen.queryByText(/Free trial active/)).not.toBeInTheDocument()
    expect(screen.queryByText(/trial ends in/i)).not.toBeInTheDocument()
  })

  it("is hidden when no subscription exists", () => {
    vi.mocked(useSubscription).mockReturnValue({ data: null } as any)
    render(<TrialBanner />)
    expect(screen.queryByText(/Free trial active/)).not.toBeInTheDocument()
  })

  it("can be dismissed and stays hidden for the same day", () => {
    vi.mocked(useSubscription).mockReturnValue({ data: mockSubscription() } as any)
    const { rerender } = render(<TrialBanner />)
    expect(screen.getByText(/Free trial active/)).toBeInTheDocument()

    const dismissBtn = screen.getByLabelText("Dismiss trial banner")
    fireEvent.click(dismissBtn)

    expect(screen.queryByText(/Free trial active/)).not.toBeInTheDocument()

    // Re-render should stay hidden
    rerender(<TrialBanner />)
    expect(screen.queryByText(/Free trial active/)).not.toBeInTheDocument()
  })
})
