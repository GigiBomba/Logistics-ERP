import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import CompanyPage from "@/pages/dashboard/company"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("CompanyPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders company page heading", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Company")).toBeInTheDocument()
  })

  it("renders company info section with company details", () => {
    render(<CompanyPage />)
    const infoHeadings = screen.getAllByText("Company Information")
    expect(infoHeadings.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("TransLogistica SRL")).toBeInTheDocument()
    expect(screen.getByText("Bucharest")).toBeInTheDocument()
    expect(screen.getByText("Romania")).toBeInTheDocument()
  })

  it("shows tabs (General / Team Management / Billing Information)", () => {
    render(<CompanyPage />)
    expect(screen.getByRole("tab", { name: /general/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /team management/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /billing information/i })).toBeInTheDocument()
  })

  it("shows company logo placeholder with initials", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Company Logo")).toBeInTheDocument()
  })

  it("shows departments section", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /team management/i }))
    expect(screen.getByText("Departments")).toBeInTheDocument()
    expect(screen.getByText("Operations")).toBeInTheDocument()
    expect(screen.getByText("Fleet")).toBeInTheDocument()
  })

  it("shows team invitations", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /team management/i }))
    expect(screen.getByText("Team Invitations")).toBeInTheDocument()
    expect(screen.getByText("new.user@translogistica.ro")).toBeInTheDocument()
  })

  it("shows quick stats sidebar", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Quick Stats")).toBeInTheDocument()
  })

  it("shows VAT information section", () => {
    render(<CompanyPage />)
    const vatEls = screen.getAllByText("VAT Information")
    expect(vatEls.length).toBeGreaterThanOrEqual(1)
  })

  it("shows actions sidebar with disabled buttons", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Upload Logo")).toBeInTheDocument()
    expect(screen.getByText("Edit Details")).toBeInTheDocument()
  })

  it("shows billing tab content", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /billing information/i }))
    const billingEls = screen.getAllByText("Billing Information")
    expect(billingEls.length).toBeGreaterThanOrEqual(1)
  })
})
