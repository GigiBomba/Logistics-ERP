import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import { useParams } from "react-router"
import OrganizationSettingsPage from "@/pages/dashboard/organization-settings"

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router")
  return { ...(actual as object), useParams: vi.fn(() => ({ slug: "translogistica" })) }
})

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("OrganizationSettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

  it("shows Save Changes button with coming soon note", () => {
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("Save Changes")).toBeInTheDocument()
    expect(screen.getByText(/Organization editing is coming soon/i)).toBeInTheDocument()
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

  it("shows Billing tab with Coming Soon callout", () => {
    render(<OrganizationSettingsPage />)
    fireEvent.click(screen.getByRole("tab", { name: /billing/i }))
    // "Billing" appears as tab name and card title
    expect(screen.getAllByText("Billing").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Coming Soon")).toBeInTheDocument()
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
  })

  it("shows not found state when slug does not match", () => {
    vi.mocked(useParams).mockReturnValue({ slug: "non-existent-org" })
    render(<OrganizationSettingsPage />)
    expect(screen.getByText("Organization not found")).toBeInTheDocument()
    expect(screen.getByText(/does not exist or you do not have access/i)).toBeInTheDocument()
    expect(screen.getByText("Back to Organizations")).toBeInTheDocument()
  })
})
