import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { fireEvent } from "@testing-library/react"
import OrganizationsPage from "@/pages/dashboard/organizations"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
}))

describe("OrganizationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "Organizations" heading and description', () => {
    render(<OrganizationsPage />)
    expect(screen.getByText("Organizations")).toBeInTheDocument()
    expect(screen.getByText(/Manage your organizations and team members/i)).toBeInTheDocument()
  })

  it("shows Organization Selector section", () => {
    render(<OrganizationsPage />)
    expect(screen.getByText("Organization Selector")).toBeInTheDocument()
  })

  it("renders all 3 organization names somewhere on the page", () => {
    render(<OrganizationsPage />)
    // Each name appears in selector card + "Current Organization" detail
    expect(screen.getAllByText("TransLogistica SRL").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("FastRoute GmbH")).toBeInTheDocument()
    expect(screen.getByText("GreenFleet Logistics")).toBeInTheDocument()
  })

  it("shows industry info on each org card", () => {
    render(<OrganizationsPage />)
    // "Logistics & Transportation" appears in org card and stats; use getAllByText
    const logisticsMatches = screen.getAllByText("Logistics & Transportation")
    expect(logisticsMatches.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Courier & Delivery")).toBeInTheDocument()
    expect(screen.getByText("Sustainable Transport")).toBeInTheDocument()
  })

  it("shows member counts on organization cards", () => {
    render(<OrganizationsPage />)
    expect(screen.getByText(/20 members/)).toBeInTheDocument()
    expect(screen.getByText(/64 members/)).toBeInTheDocument()
    expect(screen.getByText(/7 members/)).toBeInTheDocument()
  })

  it("shows plan badges on organization cards", () => {
    render(<OrganizationsPage />)
    // "Professional" appears in org card badge and Quick Stats
    expect(screen.getAllByText("Professional").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Enterprise")).toBeInTheDocument()
    expect(screen.getByText("Starter")).toBeInTheDocument()
  })

  it("shows Current badge on active organization", () => {
    render(<OrganizationsPage />)
    expect(screen.getByText("Current")).toBeInTheDocument()
  })

  it("shows user role badges on organization cards", () => {
    render(<OrganizationsPage />)
    // "Owner" appears in org card badge and Quick Stats
    expect(screen.getAllByText("Owner").length).toBe(2)
    // "Admin" and "Member" each appear once on org cards
    expect(screen.getByText("Admin")).toBeInTheDocument()
    expect(screen.getByText("Member")).toBeInTheDocument()
  })

  it("shows 'Switch to this org' buttons for non-active orgs", () => {
    render(<OrganizationsPage />)
    const switchButtons = screen.getAllByText("Switch to this org")
    expect(switchButtons.length).toBe(2)
  })

  it("shows Manage links on each org card", () => {
    render(<OrganizationsPage />)
    const manageLinks = screen.getAllByText("Manage")
    expect(manageLinks.length).toBe(3)
  })

  it("shows Current Organization detail card with org info", () => {
    render(<OrganizationsPage />)
    expect(screen.getByText("Current Organization")).toBeInTheDocument()
    // TransLogistica SRL appears in selector card AND detail card
    expect(screen.getAllByText("TransLogistica SRL").length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("Str. Logistica nr. 42, Sector 1")).toBeInTheDocument()
    expect(screen.getByText("Bucharest, Romania")).toBeInTheDocument()
    expect(screen.getByText("+40 123 456 789")).toBeInTheDocument()
    expect(screen.getByText("www.translogistica.ro")).toBeInTheDocument()
  })

  it("shows Quick Stats card", () => {
    render(<OrganizationsPage />)
    expect(screen.getByText("Quick Stats")).toBeInTheDocument()
    // "Members" appears in Quick Stats AND org card badges
    expect(screen.getAllByText("Members").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Plan")).toBeInTheDocument()
    expect(screen.getByText("Your Role")).toBeInTheDocument()
    expect(screen.getByText("Created")).toBeInTheDocument()
  })

  it("shows Create Organization section with heading and button", () => {
    render(<OrganizationsPage />)
    // "Create Organization" appears as heading and button text
    const createTexts = screen.getAllByText("Create Organization")
    expect(createTexts.length).toBe(2)
    expect(screen.getByText(/Add a new organization to your account/i)).toBeInTheDocument()
    expect(screen.getByText(/Start a new organization/i)).toBeInTheDocument()
  })

  it("shows coming soon note for organization creation", () => {
    render(<OrganizationsPage />)
    expect(screen.getByText(/Organization creation is coming soon/i)).toBeInTheDocument()
  })
})
