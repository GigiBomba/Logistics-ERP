import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import BillingPage from "@/pages/dashboard/billing"
import { companyApi } from "@/api/endpoints"
import {
  useInvoices,
  usePaymentMethods,
  useSetupIntent,
  useRemovePaymentMethod,
  useCompany,
  useUpdateCompany,
} from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useInvoices: vi.fn(),
  usePaymentMethods: vi.fn(),
  useSetupIntent: vi.fn(),
  useRemovePaymentMethod: vi.fn(),
  useCompany: vi.fn(),
  useUpdateCompany: vi.fn(),
}))

vi.mock("@/api/endpoints", () => ({
  companyApi: { update: vi.fn().mockResolvedValue({ data: {} }) },
}))

vi.mock("@/config/env", () => ({
  envConfig: {
    stripePublishableKey: "pk_test_mock",
    turnstileSiteKey: "",
    maintenanceMode: false,
  },
}))

vi.mock("@stripe/stripe-js", () => ({
  loadStripe: vi.fn(() => Promise.resolve({})),
}))

vi.mock("@stripe/react-stripe-js", () => ({
  Elements: ({ children }: any) => <div data-testid="stripe-elements">{children}</div>,
  PaymentElement: () => <div data-testid="payment-element" />,
  useStripe: () => ({ confirmSetup: vi.fn().mockResolvedValue({}) }),
  useElements: () => ({}),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

const MOCK_INVOICES = [
  {
    id: 1,
    number: "INV-2026-008",
    issued_at: "2026-08-15T00:00:00Z",
    due_at: "2026-09-15T00:00:00Z",
    amount: 99,
    currency: "EUR",
    status: "paid",
    pdf_url: "https://example.com/invoices/inv-2026-008.pdf",
  },
  {
    id: 2,
    number: "INV-2026-007",
    issued_at: "2026-07-15T00:00:00Z",
    due_at: "2026-08-15T00:00:00Z",
    amount: 149,
    currency: "EUR",
    status: "open",
    pdf_url: null,
  },
  {
    id: 3,
    number: "INV-2026-004",
    issued_at: "2026-04-15T00:00:00Z",
    due_at: null,
    amount: 0,
    currency: "EUR",
    status: "void",
    pdf_url: null,
  },
]

const MOCK_PAYMENT_METHODS = [
  {
    id: "pm_visa_4242",
    type: "card",
    card: { brand: "visa", last4: "4242", exp_month: 12, exp_year: 2028 },
    billing_details: {},
    created: "2026-08-01T00:00:00Z",
    is_default: true,
  },
  {
    id: "pm_mc_4444",
    type: "card",
    card: { brand: "mastercard", last4: "4444", exp_month: 6, exp_year: 2027 },
    billing_details: {},
    created: "2026-07-01T00:00:00Z",
    is_default: false,
  },
]

describe("BillingPage", () => {
  let removeCardMutate: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useInvoices).mockReturnValue({
      data: MOCK_INVOICES,
      isLoading: false,
      isError: false,
    } as any)
    vi.mocked(usePaymentMethods).mockReturnValue({
      data: { payment_methods: MOCK_PAYMENT_METHODS },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)
    vi.mocked(useSetupIntent).mockReturnValue({
      mutate: (_vars: undefined, opts?: any) => opts?.onSuccess?.("seti_mock_secret"),
      isPending: false,
    } as any)
    removeCardMutate = vi.fn()
    vi.mocked(useRemovePaymentMethod).mockReturnValue({
      mutate: removeCardMutate,
      isPending: false,
    } as any)
    vi.mocked(useCompany).mockReturnValue({
      data: { vat_number: "RO12345678" },
      isLoading: false,
      isError: false,
    } as any)
    vi.mocked(useUpdateCompany).mockReturnValue({
      mutate: (data: any, opts?: any) => {
        companyApi.update(data)
        opts?.onSuccess?.()
      },
      isPending: false,
    } as any)
  })

  it('renders "Billing" heading and description', () => {
    render(<BillingPage />)
    expect(screen.getByText("Billing")).toBeInTheDocument()
    expect(screen.getByText("Manage your billing information and subscription.")).toBeInTheDocument()
  })

  it("shows Invoice History card with mock invoices", () => {
    render(<BillingPage />)
    expect(screen.getByText("Invoice History")).toBeInTheDocument()
    expect(screen.getByText("INV-2026-008")).toBeInTheDocument()
    expect(screen.getByText("INV-2026-007")).toBeInTheDocument()
    expect(screen.getByText("INV-2026-004")).toBeInTheDocument()
  })

  it("shows invoice status badges", () => {
    render(<BillingPage />)
    expect(screen.getAllByText("paid").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("open")).toBeInTheDocument()
    expect(screen.getByText("void")).toBeInTheDocument()
  })

  it("shows invoice amounts and issued dates", () => {
    render(<BillingPage />)
    expect(screen.getByText("€99.00")).toBeInTheDocument()
    expect(screen.getByText(/Issued: August 15, 2026/)).toBeInTheDocument()
    expect(screen.getByText(/Due: September 15, 2026/)).toBeInTheDocument()
  })

  it("shows empty state when there are no invoices", () => {
    vi.mocked(useInvoices).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as any)
    render(<BillingPage />)
    expect(screen.getByText("No invoices yet")).toBeInTheDocument()
    expect(screen.getByText(/Your invoice history will appear here/i)).toBeInTheDocument()
  })

  it("renders saved payment methods with brand, last4 and expiry", () => {
    render(<BillingPage />)
    expect(screen.getByText("Payment Methods")).toBeInTheDocument()
    expect(screen.getByText("visa •••• 4242")).toBeInTheDocument()
    expect(screen.getByText("mastercard •••• 4444")).toBeInTheDocument()
    expect(screen.getByText("Expires 12/2028")).toBeInTheDocument()
    expect(screen.getByText("Expires 06/2027")).toBeInTheDocument()
    expect(screen.getByText("Default")).toBeInTheDocument()
  })

  it("removes a payment method after confirming", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("button", { name: "Remove visa 4242" }))
    expect(screen.getByText("Remove payment method")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Remove" }))
    expect(removeCardMutate).toHaveBeenCalledWith("pm_visa_4242", expect.anything())
  })

  it("shows empty state with an Add card button when there are no payment methods", () => {
    vi.mocked(usePaymentMethods).mockReturnValue({
      data: { payment_methods: [] },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)
    render(<BillingPage />)
    expect(screen.getByText("No payment methods")).toBeInTheDocument()
    const addButton = screen.getByRole("button", { name: "Add card" })
    expect(addButton).toBeInTheDocument()
  })

  it("opens the add card modal and requests a setup intent", () => {
    vi.mocked(usePaymentMethods).mockReturnValue({
      data: { payment_methods: [] },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("button", { name: "Add card" }))
    expect(screen.getByText("Add payment method")).toBeInTheDocument()
    expect(screen.getByTestId("payment-element")).toBeInTheDocument()
    expect(vi.mocked(useSetupIntent)).toHaveBeenCalled()
  })

  it("shows Overview card with invoice count", () => {
    render(<BillingPage />)
    expect(screen.getByText("Overview")).toBeInTheDocument()
    expect(screen.getByText("3 total")).toBeInTheDocument()
    expect(screen.getByText("View in Subscription")).toBeInTheDocument()
  })

  it("shows Tax Information card with the company VAT number", () => {
    render(<BillingPage />)
    expect(screen.getByText("Tax Information")).toBeInTheDocument()
    expect(screen.getByText("VAT / Tax ID")).toBeInTheDocument()
    expect(screen.getByText("Billing Address")).toBeInTheDocument()
    expect(screen.getByText("RO12345678")).toBeInTheDocument()
  })

  it("saves a new VAT number via companyApi.update", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("button", { name: "Edit VAT number" }))
    const input = screen.getByLabelText("VAT / Tax ID")
    fireEvent.change(input, { target: { value: "RO99999999" } })
    fireEvent.click(screen.getByRole("button", { name: "Save" }))
    expect(companyApi.update).toHaveBeenCalledWith({ vat_number: "RO99999999" })
  })

  it("shows Contact Support link", () => {
    render(<BillingPage />)
    const supportLink = screen.getByText("Contact Support").closest("a")
    expect(supportLink).toHaveAttribute("href", "mailto:support@operionerp.xyz")
  })

  it("shows loading skeleton when invoices are loading", () => {
    vi.mocked(useInvoices).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as any)
    render(<BillingPage />)
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument()
    expect(screen.queryByText("INV-2026-008")).not.toBeInTheDocument()
  })
})