import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import BillingPage from "@/pages/dashboard/billing"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("BillingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Billing" heading and description', () => {
    render(<BillingPage />)
    expect(screen.getByText("Billing")).toBeInTheDocument()
    expect(screen.getByText("Manage your billing information and subscription.")).toBeInTheDocument()
  })

  it("shows all tabs (Overview / Invoices / Payment Methods / Tax Information)", () => {
    render(<BillingPage />)
    expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /invoices/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /payment methods/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /tax information/i })).toBeInTheDocument()
  })

  it("shows Current Plan card on Overview tab", () => {
    render(<BillingPage />)
    expect(screen.getByText("Current Plan")).toBeInTheDocument()
    expect(screen.getByText("€99")).toBeInTheDocument()
    expect(screen.getAllByText(/Active/i).length).toBeGreaterThanOrEqual(1)
  })

  it("shows Next Billing info on Overview tab", () => {
    render(<BillingPage />)
    expect(screen.getAllByText("Next Billing").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/September 1, 2026/i).length).toBeGreaterThanOrEqual(1)
  })

  it("shows Usage Summary with license and storage stats", () => {
    render(<BillingPage />)
    expect(screen.getByText("Usage Summary")).toBeInTheDocument()
    expect(screen.getByText(/12 \/ 25/i)).toBeInTheDocument()
    expect(screen.getByText(/2\.3 GB \/ 10 GB/i)).toBeInTheDocument()
  })

  it("shows Billing History card on Overview tab", () => {
    render(<BillingPage />)
    expect(screen.getByText("Billing History")).toBeInTheDocument()
    expect(screen.getByText("View full invoice history and payment records.")).toBeInTheDocument()
  })

  it("shows mock invoices on Invoices tab", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /invoices/i }))
    expect(screen.getByText("INV-2026-008")).toBeInTheDocument()
    expect(screen.getByText("INV-2026-007")).toBeInTheDocument()
    expect(screen.getByText("INV-2026-004")).toBeInTheDocument()
  })

  it("shows invoice status badges", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /invoices/i }))
    expect(screen.getAllByText("paid").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("open")).toBeInTheDocument()
    expect(screen.getByText("void")).toBeInTheDocument()
  })

  it("shows empty state on Payment Methods tab", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /payment methods/i }))
    expect(screen.getByText(/Payment methods coming soon/i)).toBeInTheDocument()
    expect(screen.getByText("Add Payment Method")).toBeInTheDocument()
  })

  it("shows payment method brand icons", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /payment methods/i }))
    expect(screen.getByText("VISA")).toBeInTheDocument()
    expect(screen.getByText("MC")).toBeInTheDocument()
    expect(screen.getByText("AMEX")).toBeInTheDocument()
  })

  it("shows Billing Contact section on Payment Methods tab", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /payment methods/i }))
    expect(screen.getByText("Billing Contact")).toBeInTheDocument()
    expect(screen.getByDisplayValue("billing@example.com")).toBeInTheDocument()
  })

  it("shows Tax Information fields on Tax Info tab", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /tax information/i }))
    // "Tax Information" appears as both tab and card title
    expect(screen.getAllByText("Tax Information").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/VAT \/ Tax ID/i)).toBeInTheDocument()
    expect(screen.getByText("Billing Address")).toBeInTheDocument()
    expect(screen.getByText("Tax Exemption Certificate")).toBeInTheDocument()
  })

  it("shows Tax Settings card with callout on Tax Info tab", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /tax information/i }))
    expect(screen.getByText("Tax Settings")).toBeInTheDocument()
    expect(screen.getByText(/Tax settings will be available in a future update/i)).toBeInTheDocument()
    expect(screen.getByText("Billing Country")).toBeInTheDocument()
  })

  it("shows country select options on Tax Info tab", () => {
    render(<BillingPage />)
    fireEvent.click(screen.getByRole("tab", { name: /tax information/i }))
    expect(screen.getByText("Romania")).toBeInTheDocument()
    expect(screen.getByText("Germany")).toBeInTheDocument()
    expect(screen.getByText("United Kingdom")).toBeInTheDocument()
    expect(screen.getByText("United States")).toBeInTheDocument()
  })

  it("renders Export Billing Data button", () => {
    render(<BillingPage />)
    expect(screen.getByText("Export Billing Data")).toBeInTheDocument()
  })
})
