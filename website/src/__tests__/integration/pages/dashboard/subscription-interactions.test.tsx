import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import SubscriptionPage from "@/pages/dashboard/subscription"
import {
  useSubscription,
  useCreatePortalSession,
  useCreateCheckoutSession,
  useUpdateBillingTerm,
  useToggleAddon,
  useCancelSubscription,
  useReactivateSubscription,
} from "@/services/queries"
import { toast } from "sonner"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/services/queries", () => ({
  useSubscription: vi.fn(),
  useCreatePortalSession: vi.fn(),
  useCreateCheckoutSession: vi.fn(),
  useUpdateBillingTerm: vi.fn(),
  useToggleAddon: vi.fn(),
  useCancelSubscription: vi.fn(),
  useReactivateSubscription: vi.fn(),
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const baseSubscription = {
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

const makeMutation = (overrides: Record<string, any> = {}) => ({
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: null,
  ...overrides,
})

describe("SubscriptionPage — loading / error / empty states", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCreatePortalSession).mockReturnValue(makeMutation() as any)
    vi.mocked(useCreateCheckoutSession).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateBillingTerm).mockReturnValue(makeMutation() as any)
    vi.mocked(useToggleAddon).mockReturnValue(makeMutation({ variables: null }) as any)
    vi.mocked(useCancelSubscription).mockReturnValue(makeMutation() as any)
    vi.mocked(useReactivateSubscription).mockReturnValue(makeMutation() as any)
  })

  it("renders skeletons while loading", () => {
    vi.mocked(useSubscription).mockReturnValue({ data: undefined, isLoading: true } as any)
    render(<SubscriptionPage />)
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0)
  })

  it("renders error state with retry that refetches", () => {
    const refetch = vi.fn()
    vi.mocked(useSubscription).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
      refetch,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("Unable to load subscription")).toBeInTheDocument()
    expect(screen.getByText(/boom/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /retry/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it("renders no-subscription upgrade state and starts checkout in demo mode", async () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.({ data: { mock: true } }))
    vi.mocked(useSubscription).mockReturnValue({ data: null, isLoading: false } as any)
    vi.mocked(useCreateCheckoutSession).mockReturnValue(makeMutation({ mutate }) as any)

    render(<SubscriptionPage />)
    expect(screen.getByText("What This Means")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /upgrade/i }))
    expect(mutate).toHaveBeenCalled()
    await waitFor(() =>
      expect(toast.info).toHaveBeenCalledWith("Checkout is in demo mode — no payment is processed.")
    )
  })

  it("no-subscription checkout redirects when a real url is returned", () => {
    const mutate = vi.fn((_args, opts: any) =>
      opts?.onSuccess?.({ data: { url: "https://checkout.operion.example" } })
    )
    vi.mocked(useSubscription).mockReturnValue({ data: null, isLoading: false } as any)
    vi.mocked(useCreateCheckoutSession).mockReturnValue(makeMutation({ mutate }) as any)
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { href: "" },
    })

    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /upgrade/i }))
    expect((window.location as any).href).toBe("https://checkout.operion.example")
  })

  it("no-subscription checkout failure shows a toast", () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onError?.(new Error("x")))
    vi.mocked(useSubscription).mockReturnValue({ data: null, isLoading: false } as any)
    vi.mocked(useCreateCheckoutSession).mockReturnValue(makeMutation({ mutate }) as any)

    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /upgrade/i }))
    expect(toast.error).toHaveBeenCalledWith("Checkout failed. Please try again or contact support.")
  })
})

describe("SubscriptionPage — active subscription data state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSubscription).mockReturnValue({ data: baseSubscription, isLoading: false } as any)
    vi.mocked(useCreatePortalSession).mockReturnValue(makeMutation() as any)
    vi.mocked(useCreateCheckoutSession).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateBillingTerm).mockReturnValue(makeMutation() as any)
    vi.mocked(useToggleAddon).mockReturnValue(makeMutation({ variables: null }) as any)
    vi.mocked(useCancelSubscription).mockReturnValue(makeMutation() as any)
    vi.mocked(useReactivateSubscription).mockReturnValue(makeMutation() as any)
  })

  it("renders status badge, per-truck price and totals", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Active")).toBeInTheDocument()
    expect(screen.getByText("€99.00")).toBeInTheDocument()
    // breakdown: 5 trucks × €99.00 (appears in the row and the total)
    expect(screen.getAllByText("€495.00").length).toBeGreaterThanOrEqual(1)
  })

  it("renders current period dates", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Renews on")).toBeInTheDocument()
    expect(screen.getByText("Next billing date")).toBeInTheDocument()
  })

  it("shows trial ends row when no period end but trial ends at is set", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: { ...baseSubscription, current_period_end: null, trial_ends_at: "2026-08-20T00:00:00Z" },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("Trial ends")).toBeInTheDocument()
  })

  it("renders addon price rows and features when addons are enabled", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: {
        ...baseSubscription,
        ai_copilot_enabled: true,
        priority_support_enabled: true,
        priority_support_price_cents: 5000,
        api_access_enabled: true,
        api_access_price_cents: 3000,
      },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("AI Copilot: 5 trucks × €49.00")).toBeInTheDocument()
    expect(screen.getByText("Priority Support (fixed)")).toBeInTheDocument()
    expect(screen.getByText("API Access (fixed)")).toBeInTheDocument()
    expect(screen.getByText("Included features")).toBeInTheDocument()
  })

  it("shows annual discount, service credit and pending truck change rows", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: {
        ...baseSubscription,
        billing_term: "annual",
        annual_discount_pct: 10,
        service_credit_cents: 1500,
        pending_truck_count: 7,
      },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("Annual discount (10%)")).toBeInTheDocument()
    expect(screen.getByText("Service credit")).toBeInTheDocument()
    expect(screen.getByText("Pending change")).toBeInTheDocument()
    expect(screen.getByText("Saving 10% with annual billing")).toBeInTheDocument()
  })

  it("shows payment deferred callout", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: { ...baseSubscription, payment_deferred_until: "2026-08-30T00:00:00Z" },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("Payment deferred")).toBeInTheDocument()
    expect(screen.getByText(/Your payment has been deferred until/)).toBeInTheDocument()
  })

  it("opens the term modal for a different term and confirms the change", async () => {
    const mutate = vi.fn((_term, opts: any) => opts?.onSuccess?.())
    vi.mocked(useUpdateBillingTerm).mockReturnValue(
      makeMutation({ mutate, variables: "annual" }) as any
    )
    render(<SubscriptionPage />)

    fireEvent.click(screen.getByRole("button", { name: /^annual$/i }))
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText("Confirm billing term change")).toBeInTheDocument()
    // annual confirm text includes the discount placeholder
    expect(screen.getByText(/Switching to annual billing/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /confirm annual/i }))
    expect(mutate).toHaveBeenCalledWith("annual", expect.anything())
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("Billing term changed to annual.")
    )
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("closing term modal via keep button keeps the current term", () => {
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /^annual$/i }))
    fireEvent.click(screen.getByRole("button", { name: /keep monthly/i }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("clicking the current term does not open the modal", () => {
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /^monthly$/i }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("shows monthly switching warning when changing from annual to monthly", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: { ...baseSubscription, billing_term: "annual", annual_discount_pct: 10 },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /^monthly$/i }))
    expect(screen.getByText("Important")).toBeInTheDocument()
    expect(screen.getByText(/Annual to monthly changes may be rejected/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /confirm monthly/i }))
  })

  it("shows an error callout when term change fails", () => {
    vi.mocked(useUpdateBillingTerm).mockReturnValue(
      makeMutation({ isError: true, error: { message: "term error" } }) as any
    )
    render(<SubscriptionPage />)
    expect(screen.getByText("term error")).toBeInTheDocument()
  })

  it("toggles an addon on and fires the mutation", () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
    vi.mocked(useToggleAddon).mockReturnValue(makeMutation({ mutate, variables: null }) as any)
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("switch", { name: /toggle ai copilot/i }))
    expect(mutate).toHaveBeenCalledWith({ addon: "ai_copilot", enabled: true }, expect.anything())
    expect(toast.success).toHaveBeenCalled()
  })

  it("shows addon update error callout", () => {
    vi.mocked(useToggleAddon).mockReturnValue(
      makeMutation({ isError: true, error: { message: "addon error" }, variables: null }) as any
    )
    render(<SubscriptionPage />)
    expect(screen.getByText("addon error")).toBeInTheDocument()
  })

  it("cancels the subscription from the confirmation modal", async () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
    vi.mocked(useCancelSubscription).mockReturnValue(makeMutation({ mutate }) as any)
    render(<SubscriptionPage />)

    fireEvent.click(screen.getByRole("button", { name: /cancel subscription/i }))
    expect(screen.getByText("Cancel your subscription?")).toBeInTheDocument()
    expect(screen.getByText("You can reactivate later")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: /yes, cancel/i }))
    expect(mutate).toHaveBeenCalledWith(undefined, expect.anything())
    await waitFor(() => expect(toast.success).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("keeps the subscription when dismissing the cancel modal", () => {
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /cancel subscription/i }))
    fireEvent.click(screen.getByRole("button", { name: /keep subscription/i }))
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("shows cancel error callout inside the modal", () => {
    vi.mocked(useCancelSubscription).mockReturnValue(
      makeMutation({ isError: true, error: { message: "cancel error" } }) as any
    )
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /cancel subscription/i }))
    expect(screen.getByText("cancel error")).toBeInTheDocument()
  })

  it("starts checkout from the billing card in demo mode", async () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.({ data: { mock: true } }))
    vi.mocked(useCreateCheckoutSession).mockReturnValue(makeMutation({ mutate }) as any)
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /upgrade \/ pay/i }))
    expect(mutate).toHaveBeenCalledWith(undefined, expect.anything())
    await waitFor(() =>
      expect(toast.info).toHaveBeenCalledWith("Checkout is in demo mode — no payment is processed.")
    )
  })

  it("opens billing portal url on success", () => {
    const portalMutate = vi.fn((_args, opts: any) =>
      opts?.onSuccess?.({ data: { url: "https://portal.operion.example" } })
    )
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { href: "" },
    })
    vi.mocked(useCreatePortalSession).mockReturnValue(makeMutation({ mutate: portalMutate }) as any)
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /manage billing/i }))
    expect((window.location as any).href).toBe("https://portal.operion.example")
  })

  it("toasts when the billing portal is unavailable", () => {
    const portalMutate = vi.fn((_args, opts: any) => opts?.onError?.(new Error("x")))
    vi.mocked(useCreatePortalSession).mockReturnValue(makeMutation({ mutate: portalMutate }) as any)
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("button", { name: /manage billing/i }))
    expect(toast.error).toHaveBeenCalledWith(
      "Billing portal is not available yet. Please contact support to manage your billing."
    )
  })

  it("shows checkout error callout", () => {
    vi.mocked(useCreateCheckoutSession).mockReturnValue(
      makeMutation({ isError: true, error: { message: "checkout error" } }) as any
    )
    render(<SubscriptionPage />)
    expect(screen.getByText("checkout error")).toBeInTheDocument()
  })
})

describe("SubscriptionPage — canceled / trial variants", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCreatePortalSession).mockReturnValue(makeMutation() as any)
    vi.mocked(useCreateCheckoutSession).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateBillingTerm).mockReturnValue(makeMutation() as any)
    vi.mocked(useToggleAddon).mockReturnValue(makeMutation({ variables: null }) as any)
    vi.mocked(useCancelSubscription).mockReturnValue(makeMutation() as any)
    vi.mocked(useReactivateSubscription).mockReturnValue(makeMutation() as any)
  })

  it("renders canceled badge and reactivate flow", async () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.())
    vi.mocked(useSubscription).mockReturnValue({
      data: { ...baseSubscription, status: "canceled", current_period_end: null },
      isLoading: false,
    } as any)
    vi.mocked(useReactivateSubscription).mockReturnValue(makeMutation({ mutate }) as any)
    render(<SubscriptionPage />)

    expect(screen.getAllByText("Canceled").length).toBeGreaterThanOrEqual(1)
    fireEvent.click(screen.getByRole("button", { name: /reactivate subscription/i }))
    expect(mutate).toHaveBeenCalledWith(undefined, expect.anything())
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Subscription reactivated."))
  })

  it("shows reactivate error callout", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: { ...baseSubscription, status: "canceled", current_period_end: null },
      isLoading: false,
    } as any)
    vi.mocked(useReactivateSubscription).mockReturnValue(
      makeMutation({ isError: true, error: { message: "reactivate error" } }) as any
    )
    render(<SubscriptionPage />)
    expect(screen.getByText("reactivate error")).toBeInTheDocument()
  })

  it("shows expiring-soon header badge and warning callout with single-day unit", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: {
        ...baseSubscription,
        status: "trialing",
        current_period_end: null,
        trial_ends_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText(/Trial ends in 1d/)).toBeInTheDocument()
    expect(screen.getByText("Trial ending soon")).toBeInTheDocument()
    expect(screen.getByText(/Your trial ends in 1 day/)).toBeInTheDocument()
  })

  it("shows expired-trial warning callout", () => {
    vi.mocked(useSubscription).mockReturnValue({
      data: {
        ...baseSubscription,
        status: "trialing",
        current_period_end: null,
        trial_ends_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
      },
      isLoading: false,
    } as any)
    render(<SubscriptionPage />)
    expect(screen.getByText("Trial ended")).toBeInTheDocument()
    expect(screen.getByText(/Subscription status: trialing/)).toBeInTheDocument()
  })
})
