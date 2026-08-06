import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { OrgSwitcher } from "@/components/shared/org-switcher"
import type { Organization } from "@/types"

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

const orgs: Organization[] = [
  { id: "1", name: "Acme Logistics", industry: "Freight" },
  { id: "2", name: "Beta Transport", industry: "Fleet" },
]

beforeEach(() => {
  vi.clearAllMocks()
})

describe("OrgSwitcher", () => {
  it("renders the active organization and marks it as current", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)
    expect(screen.getByText("Acme Logistics")).toBeInTheDocument()
  })

  it("opens the dropdown listing all organizations plus footer actions", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)

    const trigger = screen.getByRole("button", { name: /acme logistics/i })
    expect(trigger).toHaveAttribute("aria-expanded", "false")

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByText("Beta Transport")).toBeInTheDocument()
    expect(screen.getByText(/manage organizations/i)).toBeInTheDocument()
    expect(screen.getByText(/create organization/i)).toBeInTheDocument()
    expect(screen.getByText("Current")).toBeInTheDocument()
  })

  it("calls onSwitch with the org id when another org is selected", () => {
    const onSwitch = vi.fn()
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={onSwitch} />)

    fireEvent.click(screen.getByRole("button", { name: /acme logistics/i }))
    // Org rows are <button role="option"> — query by option role.
    fireEvent.click(screen.getByRole("option", { name: /beta transport/i }))

    expect(onSwitch).toHaveBeenCalledWith("2")
  })

  it("supports keyboard selection (ArrowDown + Enter) for the highlighted org", () => {
    const onSwitch = vi.fn()
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={onSwitch} />)

    fireEvent.click(screen.getByRole("button", { name: /acme logistics/i }))
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "Enter" })

    expect(onSwitch).toHaveBeenCalledWith("1")
  })

  it("closes the dropdown on Escape", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)

    const trigger = screen.getByRole("button", { name: /acme logistics/i })
    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute("aria-expanded", "true")

    fireEvent.keyDown(document, { key: "Escape" })
    expect(trigger).toHaveAttribute("aria-expanded", "false")
  })

  it("shows a placeholder when no organization is active", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="nope" onSwitch={vi.fn()} />)
    expect(screen.getByText("Select Organization")).toBeInTheDocument()
  })

  it("closes the dropdown when clicking outside", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)
    const trigger = screen.getByRole("button", { name: /acme logistics/i })
    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute("aria-expanded", "true")

    fireEvent.mouseDown(document.body)
    expect(trigger).toHaveAttribute("aria-expanded", "false")
  })

  it("does not close when clicking inside the container", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)
    const trigger = screen.getByRole("button", { name: /acme logistics/i })
    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute("aria-expanded", "true")

    fireEvent.mouseDown(trigger)
    expect(trigger).toHaveAttribute("aria-expanded", "true")
  })

  it("supports ArrowUp + Enter to select the highlighted org", () => {
    const onSwitch = vi.fn()
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={onSwitch} />)
    fireEvent.click(screen.getByRole("button", { name: /acme logistics/i }))
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "ArrowUp" })
    fireEvent.keyDown(document, { key: "Enter" })
    expect(onSwitch).toHaveBeenCalledWith("1")
  })

  it("cycles the highlight from the last org back to the first on ArrowDown", () => {
    const onSwitch = vi.fn()
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={onSwitch} />)
    fireEvent.click(screen.getByRole("button", { name: /acme logistics/i }))
    // index -1 -> 0 -> 1 -> 2 (manage) -> 3 (create) -> 0 (wrap)
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "Enter" })
    expect(onSwitch).toHaveBeenCalledWith("1")
  })

  it("closes the dropdown when Enter is pressed on the manage link highlight", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)
    const trigger = screen.getByRole("button", { name: /acme logistics/i })
    fireEvent.click(trigger)
    // ArrowDown twice highlights index 2 (Manage organizations)
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "ArrowDown" })
    fireEvent.keyDown(document, { key: "Enter" })
    expect(trigger).toHaveAttribute("aria-expanded", "false")
  })

  it("highlights an organization row on mouse enter and selects it with Enter", () => {
    const onSwitch = vi.fn()
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={onSwitch} />)
    fireEvent.click(screen.getByRole("button", { name: /acme logistics/i }))
    const option = screen.getByRole("option", { name: /beta transport/i })
    fireEvent.mouseEnter(option)
    fireEvent.keyDown(document, { key: "Enter" })
    expect(onSwitch).toHaveBeenCalledWith("2")
  })

  it("closes the dropdown with Tab when focus leaves the container", async () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)
    const trigger = screen.getByRole("button", { name: /acme logistics/i })
    fireEvent.click(trigger)
    fireEvent.keyDown(document, { key: "Tab" })
    await waitFor(() => {
      expect(trigger).toHaveAttribute("aria-expanded", "false")
    })
  })

  it("switching orgs via click closes the dropdown", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)
    const trigger = screen.getByRole("button", { name: /acme logistics/i })
    fireEvent.click(trigger)
    fireEvent.click(screen.getByRole("option", { name: /beta transport/i }))
    expect(trigger).toHaveAttribute("aria-expanded", "false")
  })

  it("shows the org industry in the option list", () => {
    render(<OrgSwitcher organizations={orgs} activeOrgId="1" onSwitch={vi.fn()} />)
    fireEvent.click(screen.getByRole("button", { name: /acme logistics/i }))
    expect(screen.getByText("Freight")).toBeInTheDocument()
    expect(screen.getByText("Fleet")).toBeInTheDocument()
  })
})
