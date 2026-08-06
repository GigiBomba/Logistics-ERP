import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import CompanyPage from "@/pages/dashboard/company"
import {
  useCompany,
  useOrganizationMembers,
  useOrganizationInvitations,
  useLicenses,
} from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useCompany: vi.fn(),
  useOrganizationMembers: vi.fn(),
  useOrganizationInvitations: vi.fn(),
  useLicenses: vi.fn(),
  useInviteMember: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

const mockCompany = {
  company_name: "TransLogistica SRL",
  name: "TransLogistica SRL",
  address: "123 Main St",
  city: "Bucharest",
  country: "Romania",
  postal_code: "010101",
  phone: "+40 21 123 4567",
  website: "https://translogistica.ro",
  subscription_tier: "professional",
  vat_number: "RO12345678",
}

const mockMembers = [
  { id: "1", email: "admin@translogistica.ro", role: "admin", status: "active" },
  { id: "2", email: "user@translogistica.ro", role: "member", status: "active" },
  { id: "3", email: "new.user@translogistica.ro", role: "member", status: "pending" },
  { id: "4", email: "driver1@translogistica.ro", role: "member", status: "pending" },
]

const mockLicenses = [{ id: "1", seats: 25, seats_used: 5 }]

describe("CompanyPage (Enhanced)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCompany).mockReturnValue({ data: mockCompany, isLoading: false } as any)
    vi.mocked(useOrganizationMembers).mockReturnValue({ data: mockMembers, isLoading: false } as any)
    vi.mocked(useOrganizationInvitations).mockReturnValue({ data: [], isLoading: false } as any)
    vi.mocked(useLicenses).mockReturnValue({ data: mockLicenses, isLoading: false } as any)
  })

  it("renders company page heading", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Company")).toBeInTheDocument()
  })

  it("renders company info section with company details", () => {
    render(<CompanyPage />)
    expect(screen.getAllByText("Company Information").length).toBeGreaterThanOrEqual(1)
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

  it("shows company logo placeholder", () => {
    render(<CompanyPage />)
    expect(screen.getAllByText("Company Logo").length).toBeGreaterThanOrEqual(1)
  })

  it("shows quick stats sidebar", () => {
    render(<CompanyPage />)
    expect(screen.getByText("Quick Stats")).toBeInTheDocument()
    expect(screen.getByText("Team Size")).toBeInTheDocument()
    expect(screen.getByText("Plan")).toBeInTheDocument()
  })

  it("shows team tab", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /team management/i }))
    expect(screen.getAllByText("Team Management").length).toBeGreaterThanOrEqual(1)
  })

  it("shows billing tab content", () => {
    render(<CompanyPage />)
    fireEvent.click(screen.getByRole("tab", { name: /billing information/i }))
    expect(screen.getAllByText("Billing Information").length).toBeGreaterThanOrEqual(1)
  })
})
