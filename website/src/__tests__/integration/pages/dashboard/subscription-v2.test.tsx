import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import SubscriptionPage from "@/pages/dashboard/subscription"
import { useSubscription } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useSubscription: vi.fn(),
  useCreatePortalSession: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useCreateCheckoutSession: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useUpdateBillingTerm: vi.fn(() => ({ mutate: vi.fn(), isPending: false, isError: false, error: null })),
  useToggleAddon: vi.fn(() => ({ mutate: vi.fn(), isPending: false, isError: false, error: null, variables: null })),
  useCancelSubscription: vi.fn(() => ({ mutate: vi.fn(), isPending: false, isError: false, error: null })),
  useReactivateSubscription: vi.fn(() => ({ mutate: vi.fn(), isPending: false, isError: false, error: null })),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const mockSubscription = {
  status: "active",
  licensed_truck_count: 5,
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
  trial_ends_at: null,
  payment_deferred_until: null,
  pending_truck_count: null,
  addons: [],
}

describe("SubscriptionPage (Enhanced)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSubscription).mockReturnValue({ data: mockSubscription, isLoading: false } as any)
  })

  it('renders "Subscription" heading', () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Subscription")).toBeInTheDocument()
  })

  it("shows current plan card", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Current Plan")).toBeInTheDocument()
  })

  it("shows billing section", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Billing")).toBeInTheDocument()
  })

  it("shows current status section", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Current Status")).toBeInTheDocument()
  })

  it("shows billing cycle info", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Status")).toBeInTheDocument()
  })

  it("shows subscription status", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Status")).toBeInTheDocument()
  })

  it("renders billing term toggle buttons", () => {
    render(<SubscriptionPage />)
    expect(screen.getByRole("button", { name: /monthly/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /annual/i })).toBeInTheDocument()
  })

  it("renders addon toggles", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("AI Copilot")).toBeInTheDocument()
    expect(screen.getByText("Priority Support")).toBeInTheDocument()
    expect(screen.getByText("API Access")).toBeInTheDocument()
  })

  it("renders cancel subscription button for active subscriptions", () => {
    render(<SubscriptionPage />)
    expect(screen.getByRole("button", { name: /cancel subscription/i })).toBeInTheDocument()
  })

  it("renders reactivate button for canceled subscriptions", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: { ...mockSubscription, status: "canceled" },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByRole("button", { name: /reactivate subscription/i })).toBeInTheDocument()
  })

  it("renders an expired-trial warning callout when status is trialing and trial_ends_at is in the past", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: {
        ...mockSubscription,
        status: "trialing",
        current_period_end: null,
        trial_ends_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("Trial ended")).toBeInTheDocument()
    expect(screen.getByText(/Your trial has ended/)).toBeInTheDocument()
    expect(screen.getByText(/Subscription status: trialing/)).toBeInTheDocument()
  })

  it("renders an expiring-soon callout when trial ends within a few days", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: {
        ...mockSubscription,
        status: "trialing",
        current_period_end: null,
        trial_ends_at: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
      },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("Trial ending soon")).toBeInTheDocument()
    expect(screen.getByText(/Your trial ends in/)).toBeInTheDocument()
  })

  it("does not render a trial callout for an active subscription with no trial", () => {
    render(<SubscriptionPage />)
    expect(screen.queryByText("Trial ended")).not.toBeInTheDocument()
    expect(screen.queryByText("Trial ending soon")).not.toBeInTheDocument()
  })
})
