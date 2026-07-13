import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import SubscriptionPage from "@/pages/dashboard/subscription"
import { useInvoices } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useInvoices: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("SubscriptionPage (Enhanced)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useInvoices).mockReturnValue({
      data: null,
      isLoading: false,
    } as any)
  })

  it('renders "Subscription" heading', () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Subscription")).toBeInTheDocument()
  })

  it("shows current plan card with pricing", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Current Plan")).toBeInTheDocument()
    expect(screen.getByText("€99")).toBeInTheDocument()
    expect(screen.getByText("/month")).toBeInTheDocument()
  })

  it("shows billing status", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Billing Status")).toBeInTheDocument()
    expect(screen.getByText("Paid")).toBeInTheDocument()
    expect(screen.getByText("5 / 25")).toBeInTheDocument()
  })

  it("shows tabs (Plan / Billing / History)", () => {
    render(<SubscriptionPage />)
    expect(screen.getByRole("tab", { name: /^plan$/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /^billing$/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /^history$/i })).toBeInTheDocument()
  })

  it("shows invoice history with mock invoices", () => {
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("tab", { name: /^history$/i }))
    expect(screen.getByText("INV-2026-008")).toBeInTheDocument()
    expect(screen.getByText("INV-2026-007")).toBeInTheDocument()
    expect(screen.getByText("INV-2026-006")).toBeInTheDocument()
  })

  it("shows payment methods placeholder in Billing tab", () => {
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("tab", { name: /^billing$/i }))
    expect(screen.getByText("Payment Methods")).toBeInTheDocument()
    expect(screen.getByText("No payment methods")).toBeInTheDocument()
  })

  it("shows upgrade recommendation", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Upgrade Recommendation")).toBeInTheDocument()
    expect(screen.getByText(/upgrading.*Enterprise/i)).toBeInTheDocument()
  })

  it("shows renewal information card", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Renewal Information")).toBeInTheDocument()
    // "Sep 1, 2026" appears in multiple places on the page
    expect(screen.getAllByText("Sep 1, 2026").length).toBeGreaterThanOrEqual(1)
  })

  it("shows feature comparison table", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Feature Comparison")).toBeInTheDocument()
    expect(screen.getByText("Starter")).toBeInTheDocument()
    expect(screen.getByText("Professional")).toBeInTheDocument()
    expect(screen.getByText("Enterprise")).toBeInTheDocument()
  })

  it("shows subscription timeline", () => {
    render(<SubscriptionPage />)
    expect(screen.getByText("Subscription Timeline")).toBeInTheDocument()
    expect(screen.getByText("Plan Renewal")).toBeInTheDocument()
    expect(screen.getByText("Trial Started")).toBeInTheDocument()
  })

  it("shows coupon code input placeholder on billing tab", () => {
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("tab", { name: /^billing$/i }))
    expect(screen.getByText("Coupon Code")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("Enter code")).toBeInTheDocument()
  })

  it("shows upgrade/downgrade placeholders on billing tab", () => {
    render(<SubscriptionPage />)
    fireEvent.click(screen.getByRole("tab", { name: /^billing$/i }))
    expect(screen.getByText("Upgrade Plan")).toBeInTheDocument()
    expect(screen.getByText("Downgrade Plan")).toBeInTheDocument()
  })
})
