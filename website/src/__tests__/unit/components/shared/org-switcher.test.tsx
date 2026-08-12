import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import { OrgSwitcher } from "@/components/shared/org-switcher"

vi.mock("motion/react", () => {
  const MotionComponent = (props: any) => {
    const { children, ...rest } = props
    return <div {...rest}>{children}</div>
  }
  return {
    motion: new Proxy(
      {},
      {
        get: () => MotionComponent,
      }
    ),
    AnimatePresence: ({ children }: any) => <>{children}</>,
  }
})

vi.mock("@/i18n/locale-context", async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useLocale: () => ({
      t: (key: string) => key,
    }),
  }
})

const MOCK_ORGS = [
  { id: "org-1", name: "Acme Corp", industry: "Logistics" },
  { id: "org-2", name: "Globex Inc", industry: "Manufacturing" },
  { id: "org-3", name: "Initech", industry: "Technology" },
]

function getDefaultProps(overrides = {}) {
  return {
    organizations: MOCK_ORGS,
    activeOrgId: "org-1",
    onSwitch: vi.fn(),
    ...overrides,
  }
}

describe("OrgSwitcher", () => {
  it("renders the current organization name", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    expect(screen.getByText("Acme Corp")).toBeInTheDocument()
  })

  it("renders initials of the active organization in the trigger", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    // The trigger shows initials "AC" for "Acme Corp"
    const initialsElements = screen.getAllByText("AC")
    expect(initialsElements.length).toBeGreaterThanOrEqual(1)
  })

  it("shows placeholder text when no active org is found", () => {
    render(<OrgSwitcher {...getDefaultProps({ activeOrgId: "nonexistent" })} />)
    expect(screen.getByText("Select Organization")).toBeInTheDocument()
  })

  it("renders a fallback Building2 icon when no active org", () => {
    const { container } = render(
      <OrgSwitcher {...getDefaultProps({ activeOrgId: "nonexistent" })} />
    )
    const buildingIcon = container.querySelector(".lucide-building2")
    expect(buildingIcon).toBeInTheDocument()
  })

  it("opens the dropdown when the trigger is clicked", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    const trigger = screen.getByRole("button", { expanded: false })
    fireEvent.click(trigger)
    // The listbox is wrapped in a motion.div; check for a visible option instead
    expect(screen.getByRole("option", { name: /acme corp/i })).toBeInTheDocument()
  })

  it("displays all organizations in the dropdown", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    // Each org name appears in both trigger and dropdown, so use getAllByText
    for (const org of MOCK_ORGS) {
      const elements = screen.getAllByText(org.name)
      expect(elements.length).toBeGreaterThanOrEqual(1)
    }
  })

  it("displays industry for each organization", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    expect(screen.getByText("Logistics")).toBeInTheDocument()
    expect(screen.getByText("Manufacturing")).toBeInTheDocument()
    expect(screen.getByText("Technology")).toBeInTheDocument()
  })

  it("shows Current badge for the active organization", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    const badges = screen.getAllByText("Current")
    expect(badges.length).toBe(1)
  })

  it("sets aria-selected on the active org option", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    const options = screen.getAllByRole("option")
    const activeOption = options.find((o) => o.getAttribute("aria-selected") === "true")
    expect(activeOption).toBeInTheDocument()
    expect(activeOption).toHaveTextContent("Acme Corp")
  })

  it("calls onSwitch when clicking a different organization", () => {
    const onSwitch = vi.fn()
    render(<OrgSwitcher {...getDefaultProps({ onSwitch })} />)
    fireEvent.click(screen.getByRole("button"))

    fireEvent.click(screen.getByText("Globex Inc"))
    expect(onSwitch).toHaveBeenCalledWith("org-2")
  })

  it("closes the dropdown after switching organization", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    // Click an org name in the dropdown
    const orgButtons = screen.getAllByText("Globex Inc")
    fireEvent.click(orgButtons[orgButtons.length - 1])

    // Dropdown should close — options should not be visible
    expect(screen.queryAllByRole("option").length).toBe(0)
  })

  it("renders Manage organizations link", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    const manageLink = screen.getByText("Manage organizations")
    expect(manageLink).toBeInTheDocument()
    expect(manageLink.closest("a")).toHaveAttribute("href", "/dashboard/organizations")
  })

  it("renders Create organization button as disabled", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    const createBtn = screen.getByText("Create organization").closest("button")!
    expect(createBtn).toBeDisabled()
  })

  it("shows Soon label on the Create organization button", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    expect(screen.getByText("Soon")).toBeInTheDocument()
  })

  it("closes the dropdown when clicking outside", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    // Click outside on document body
    fireEvent.mouseDown(document.body)

    // Dropdown should close — options should be gone
    expect(screen.queryAllByRole("option").length).toBe(0)
  })

  it("closes the dropdown on Escape key", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    fireEvent.keyDown(document, { key: "Escape" })

    expect(screen.queryAllByRole("option").length).toBe(0)
  })

  it("toggles dropdown on trigger click", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    const trigger = screen.getByRole("button")

    // Open
    fireEvent.click(trigger)
    expect(screen.getAllByRole("option").length).toBeGreaterThan(0)

    // Close (toggle)
    fireEvent.click(trigger)
    expect(screen.queryAllByRole("option").length).toBe(0)
  })

  it("sets aria-expanded on the trigger button", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    const trigger = screen.getByRole("button")

    expect(trigger.getAttribute("aria-expanded")).toBe("false")
    fireEvent.click(trigger)
    expect(trigger.getAttribute("aria-expanded")).toBe("true")
  })

  it("sets aria-haspopup on the trigger button", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    const trigger = screen.getByRole("button")
    expect(trigger.getAttribute("aria-haspopup")).toBe("listbox")
  })

  it("renders initials for each org in the dropdown", () => {
    render(<OrgSwitcher {...getDefaultProps()} />)
    fireEvent.click(screen.getByRole("button"))

    // AC appears in both trigger and dropdown
    const acElements = screen.getAllByText("AC")
    expect(acElements.length).toBe(2)

    expect(screen.getByText("GI")).toBeInTheDocument()
    expect(screen.getByText("I")).toBeInTheDocument()
  })

  it("handles single-word org names for initials", () => {
    const orgs = [{ id: "org-4", name: "Apple", industry: "Tech" }]
    render(<OrgSwitcher {...getDefaultProps({ organizations: orgs, activeOrgId: "org-4" })} />)
    fireEvent.click(screen.getByRole("button"))

    // "A" appears in both trigger and dropdown
    const aElements = screen.getAllByText("A")
    expect(aElements.length).toBe(2)
  })

  it("handles three-word org names for initials", () => {
    const orgs = [{ id: "org-5", name: "The Big Corp", industry: "Finance" }]
    render(
      <OrgSwitcher {...getDefaultProps({ organizations: orgs, activeOrgId: "org-5" })} />
    )
    fireEvent.click(screen.getByRole("button"))

    // "TB" appears in both trigger and dropdown
    const tbElements = screen.getAllByText("TB")
    expect(tbElements.length).toBe(2)
  })

  it("rotates chevron icon when dropdown is open", () => {
    const { container } = render(<OrgSwitcher {...getDefaultProps()} />)
    const chevron = container.querySelector(".lucide-chevron-down")!

    expect(chevron.getAttribute("class")).not.toContain("rotate-180")
    fireEvent.click(screen.getByRole("button"))
    expect(chevron.getAttribute("class")).toContain("rotate-180")
  })
})
