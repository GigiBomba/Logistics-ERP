import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import { useParams } from "react-router"
import OrganizationSettingsPage from "@/pages/dashboard/organization-settings"
import { useOrganization, useOrganizationMembers, useOrganizationInvitations } from "@/services/queries"

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router")
  return { ...(actual as object), useParams: vi.fn(() => ({ slug: "translogistica" })) }
})

vi.mock("@/services/queries", () => ({
  useOrganization: vi.fn(),
  useOrganizationMembers: vi.fn(),
  useOrganizationInvitations: vi.fn(),
  useUpdateOrganization: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useInviteMember: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useRemoveMember: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

const TRANSLOGISTICA_ORG = {
  id: "org-1",
  name: "TransLogistica SRL",
  slug: "translogistica",
  industry: "Logistics & Transportation",
  subscription_tier: "professional",
  user_role: "owner",
  size: "51-200",
  address: "Str. Logistica nr. 42, Sector 1",
  city: "Bucharest",
  country: "Romania",
  postal_code: "012345",
  phone: "+40 123 456 789",
  website: "www.translogistica.ro",
  created_at: "2023-01-01T00:00:00Z",
  updated_at: "2026-07-01T12:00:00Z",
}

const MOCK_MEMBERS = [
  { id: 1, name: "Alexandru Marin", email: "alexandru@translogistica.ro", role: "owner", joined_at: "2023-01-01T00:00:00Z" },
  { id: 2, name: "Maria Dumitrescu", email: "maria@translogistica.ro", role: "admin", joined_at: "2023-02-01T00:00:00Z" },
  { id: 3, name: "Ion Popescu", email: "ion@translogistica.ro", role: "admin", joined_at: "2024-05-01T00:00:00Z" },
  { id: 4, name: "Elena Radu", email: "elena@translogistica.ro", role: "member", joined_at: "2025-03-01T00:00:00Z" },
  { id: 5, name: "Andrei Stancu", email: "andrei@translogistica.ro", role: "member", joined_at: "2026-01-10T00:00:00Z" },
]

const MOCK_INVITATIONS = [
  { id: 1, email: "new.dispatcher@translogistica.ro", role: "member", status: "pending", invited_by_name: "Alexandru Marin", created_at: "2026-08-20T10:00:00Z" },
]

function mockOrgQueries() {
  vi.mocked(useOrganization).mockImplementation((slug: string) => ({
    data: slug === "translogistica" ? TRANSLOGISTICA_ORG : undefined,
    isLoading: false,
    isError: false,
  } as any))
  vi.mocked(useOrganizationMembers).mockReturnValue({
    data: MOCK_MEMBERS,
    isLoading: false,
    isError: false,
  } as any)
  vi.mocked(useOrganizationInvitations).mockReturnValue({
    data: MOCK_INVITATIONS,
    isLoading: false,
    isError: false,
  } as any)
}

describe("OrganizationSettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockOrgQueries()
  })

  it("shows back link to organizations", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("Back to Organizations")).toBeInTheDocument()
  })

  it("renders organization name in header", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("TransLogistica SRL")).toBeInTheDocument()
  })

  it("shows all tabs (General / Members / Billing / Danger Zone)", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByRole("tab", { name: /general/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /members/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /billing/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /danger zone/i })).toBeInTheDocument()
  })

  it("shows General Information card on General tab", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("General Information")).toBeInTheDocument()
    expect(screen.getByText(/Update your organization profile/i)).toBeInTheDocument()
  })

  it("shows form fields on General tab", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("Organization Name")).toBeInTheDocument()
    expect(screen.getByText("Slug")).toBeInTheDocument()
    expect(screen.getByText("Industry")).toBeInTheDocument()
    expect(screen.getByText("Size")).toBeInTheDocument()
    expect(screen.getByText("Address")).toBeInTheDocument()
    expect(screen.getByText("City")).toBeInTheDocument()
    expect(screen.getByText("Country")).toBeInTheDocument()
    expect(screen.getByText("Postal Code")).toBeInTheDocument()
    expect(screen.getByText("Phone")).toBeInTheDocument()
    expect(screen.getByText("Website")).toBeInTheDocument()
  })

  it("shows pre-filled org data in form fields", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByDisplayValue("TransLogistica SRL")).toBeInTheDocument()
    expect(screen.getByDisplayValue("translogistica")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Str. Logistica nr. 42, Sector 1")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Bucharest")).toBeInTheDocument()
    expect(screen.getByDisplayValue("Romania")).toBeInTheDocument()
    expect(screen.getByDisplayValue("www.translogistica.ro")).toBeInTheDocument()
  })

  it("shows Details card with created and last updated dates", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("Details")).toBeInTheDocument()
    expect(screen.getByText("Created")).toBeInTheDocument()
    expect(screen.getByText("Last Updated")).toBeInTheDocument()
    expect(screen.getByText("ID")).toBeInTheDocument()
    expect(screen.getByText("org-1")).toBeInTheDocument()
  })

  it("shows Save Changes button when editing is started", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("Edit Organization")).toBeInTheDocument()
    fireEvent.click(screen.getByText("Edit Organization"))
    expect(screen.getByText("Save Changes")).toBeInTheDocument()
  })

  it("shows Members tab with member list and roles", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /members/i }))
    // "Members" appears as tab, card title, and tab content heading
    expect(screen.getAllByText("Members").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Alexandru Marin")).toBeInTheDocument()
    expect(screen.getByText("Maria Dumitrescu")).toBeInTheDocument()
    expect(screen.getByText("Ion Popescu")).toBeInTheDocument()
    expect(screen.getByText("Elena Radu")).toBeInTheDocument()
    expect(screen.getByText("Andrei Stancu")).toBeInTheDocument()
  })

  it("shows member roles on Members tab", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /members/i }))
    expect(screen.getByText("Owner")).toBeInTheDocument()
    // There are multiple Admin and Member badges
    const adminBadges = screen.getAllByText("Admin")
    expect(adminBadges.length).toBeGreaterThanOrEqual(2)
    const memberBadges = screen.getAllByText("Member")
    expect(memberBadges.length).toBeGreaterThanOrEqual(2)
  })

  it("shows Invite Member form on Members tab", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /members/i }))
    expect(screen.getByText("Invite Member")).toBeInTheDocument()
    expect(screen.getByText("Email Address")).toBeInTheDocument()
    expect(screen.getByText("Role")).toBeInTheDocument()
    expect(screen.getByText("Send Invitation")).toBeInTheDocument()
  })

  it("shows Pending Invitations section on Members tab", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /members/i }))
    expect(screen.getByText("Pending Invitations")).toBeInTheDocument()
    expect(screen.getByText("new.dispatcher@translogistica.ro")).toBeInTheDocument()
    expect(screen.getByText("Pending")).toBeInTheDocument()
  })

  it("shows Billing tab with under-development note", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /billing/i }))
    // "Billing" appears as tab name and card title
    expect(screen.getAllByText("Billing").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/Detailed billing management is under development/i)).toBeInTheDocument()
    expect(screen.getByText("Current Plan")).toBeInTheDocument()
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("shows Danger Zone tab with delete button", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /danger zone/i }))
    // "Danger Zone" appears as tab name and card title
    expect(screen.getAllByText("Danger Zone").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/Destructive actions that cannot be undone/i)).toBeInTheDocument()
    // "Delete Organization" appears as paragraph text and button label
    expect(screen.getAllByText("Delete Organization").length).toBeGreaterThanOrEqual(1)
  })

  it("shows warning callout on Danger Zone tab", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /danger zone/i }))
    expect(screen.getByText("Warning")).toBeInTheDocument()
    expect(screen.getByText(/permanently remove all associated data/i)).toBeInTheDocument()
  })
})

describe("OrganizationSettingsPage - Not Found", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockOrgQueries()
  })

  it("shows not found state when slug does not match", () => {
    vi.mocked(useParams).mockReturnValue({ slug: "non-existent-org" })
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("Organization not found")).toBeInTheDocument()
    expect(screen.getByText(/does not exist or you do not have access/i)).toBeInTheDocument()
    expect(screen.getByText("Back to Organizations")).toBeInTheDocument()
  })
})
