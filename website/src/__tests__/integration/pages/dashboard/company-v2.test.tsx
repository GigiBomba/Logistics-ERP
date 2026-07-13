import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import CompanyPage from "@/pages/dashboard/company"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("CompanyPage (Enhanced)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders company page heading", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Company")).toBeInTheDocument()
  })

  it("renders company info section with company details", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Company Information")).toBeInTheDocument()
    expect(screen.getByText("TransLogistica SRL")).toBeInTheDocument()
    expect(screen.getByText("Bucharest")).toBeInTheDocument()
    expect(screen.getByText("Romania")).toBeInTheDocument()
  })

  it("shows tabs (Overview / Team / Billing)", () => {
    render(<CompanyPage />)
    expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /team/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /billing/i })).toBeInTheDocument()
  })

  it("shows company logo placeholder with initials", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Company Logo")).toBeInTheDocument()
    expect(screen.getByText("TL")).toBeInTheDocument()
  })

  it("shows departments section", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /team/i }))
    expect(screen.getByText("Departments")).toBeInTheDocument()
    expect(screen.getByText("Operations")).toBeInTheDocument()
    expect(screen.getByText("Fleet")).toBeInTheDocument()
    expect(screen.getByText("Dispatch")).toBeInTheDocument()
    expect(screen.getByText("Finance")).toBeInTheDocument()
  })

  it("shows team invitations with email and role", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /team/i }))
    expect(screen.getByText("Team Invitations")).toBeInTheDocument()
    expect(screen.getByText("new.user@translogistica.ro")).toBeInTheDocument()
    expect(screen.getByText("driver1@translogistica.ro")).toBeInTheDocument()
  })

  it("shows quick stats sidebar", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Quick Stats")).toBeInTheDocument()
    expect(screen.getByText("Team Size")).toBeInTheDocument()
    expect(screen.getByText("Departments")).toBeInTheDocument()
    expect(screen.getByText("Plan")).toBeInTheDocument()
    expect(screen.getByText("Licenses Used")).toBeInTheDocument()
  })

  it("shows VAT information section", () => {
    render(<CompanyPage />)
    expect(screen.getByText("VAT Information")).toBeInTheDocument()
  })

  it("shows actions sidebar with disabled buttons", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Actions")).toBeInTheDocument()
    expect(screen.getByText("Upload Logo")).toBeInTheDocument()
    expect(screen.getByText("Edit Details")).toBeInTheDocument()
  })

  it("shows employee overview in Team tab", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /team/i }))
    expect(screen.getByText("Employee Overview")).toBeInTheDocument()
    expect(screen.getByText("Total Employees")).toBeInTheDocument()
    expect(screen.getByText("Active Users")).toBeInTheDocument()
  })

  it("shows billing tab content", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /billing/i }))
    expect(screen.getByText("Billing Information")).toBeInTheDocument()
  })

  it("shows coming soon callout for department management", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /team/i }))
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
  })
})
