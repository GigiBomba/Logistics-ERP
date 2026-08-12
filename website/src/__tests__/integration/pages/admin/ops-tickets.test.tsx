import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import OpsTicketsPage from "@/pages/admin/ops/tickets"

const { useOpsTicketsMock, useOpsTicketMock } = vi.hoisted(() => ({
  useOpsTicketsMock: vi.fn(),
  useOpsTicketMock: vi.fn(),
}))

vi.mock("@/services/queries", () => ({
  useOpsTickets: useOpsTicketsMock,
  useOpsTicket: useOpsTicketMock,
}))

const { motionMock } = vi.hoisted(() => {
  const MockMotionDiv = ({ children, ...rest }: any) => <div {...rest}>{children}</div>
  return {
    motionMock: new Proxy({}, { get: () => MockMotionDiv }),
  }
})

vi.mock("motion/react", () => ({
  motion: motionMock,
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useInView: () => true,
}))

const ticket = {
  issue_id: "ISS-1",
  summary: "Login fails after MFA",
  risk_tier: "high",
  status: "open",
  company_id: "C-1",
  created_at: "2026-06-01T00:00:00Z",
}

const detail = {
  ...ticket,
  reproduction_steps: ["Open app", "Try to log in"],
  logs: "ERROR: token expired",
  customer_id: "C-1",
  environment: "production",
  app_version: "4.2.0",
  suspected_module: "auth",
  linked_known_issue_id: "KNOWN-9",
  confidence_at_escalation: 0.8,
  attachments: [{ name: "trace.log" }],
}

describe("OpsTicketsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useOpsTicketsMock.mockReturnValue({ data: [ticket], isLoading: false, isError: false })
    useOpsTicketMock.mockReturnValue({ data: undefined, isLoading: false })
  })

  it("shows a loading spinner while loading", () => {
    useOpsTicketsMock.mockReturnValue({ data: undefined, isLoading: true, isError: false })
    render(<OpsTicketsPage />)
    expect(document.querySelector("svg")).toBeInTheDocument()
  })

  it("shows an error state when loading fails", () => {
    useOpsTicketsMock.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    render(<OpsTicketsPage />)
    expect(screen.getByText(/failed to load tickets/i)).toBeInTheDocument()
  })

  it("shows an empty state when there are no tickets", () => {
    useOpsTicketsMock.mockReturnValue({ data: [], isLoading: false, isError: false })
    render(<OpsTicketsPage />)
    expect(screen.getAllByText(/no tickets/i).length).toBeGreaterThan(0)
  })

  it("renders ticket rows with risk and status badges", () => {
    render(<OpsTicketsPage />)
    expect(screen.getByText("ISS-1")).toBeInTheDocument()
    expect(screen.getByText("Login fails after MFA")).toBeInTheDocument()
    expect(screen.getAllByText("High").length).toBeGreaterThan(0)
    expect(screen.getByText("open")).toBeInTheDocument()
  })

  it("passes filters to the tickets query", () => {
    render(<OpsTicketsPage />)
    const selects = screen.getAllByRole("combobox")
    fireEvent.change(selects[0], { target: { value: "high" } })
    expect(useOpsTicketsMock).toHaveBeenCalledWith({ risk_tier: "high" })

    fireEvent.change(selects[1], { target: { value: "resolved" } })
    expect(useOpsTicketsMock).toHaveBeenLastCalledWith({
      risk_tier: "high",
      status: "resolved",
    })
  })

  it("opens the detail panel when a ticket row is clicked", () => {
    useOpsTicketMock.mockReturnValue({ data: detail, isLoading: false })
    render(<OpsTicketsPage />)
    fireEvent.click(screen.getByText("Login fails after MFA"))
    expect(screen.getByText(/reproduction steps/i)).toBeInTheDocument()
    expect(screen.getByText("ERROR: token expired")).toBeInTheDocument()
    expect(screen.getByText("KNOWN-9")).toBeInTheDocument()
    expect(screen.getByText("80%")).toBeInTheDocument()
    expect(screen.getByText("trace.log")).toBeInTheDocument()
  })

  it("closes the detail panel", () => {
    useOpsTicketMock.mockReturnValue({ data: detail, isLoading: false })
    render(<OpsTicketsPage />)
    fireEvent.click(screen.getByText("Login fails after MFA"))
    const close = screen.getAllByRole("button").find((b) => b.querySelector("svg"))
    fireEvent.click(close!)
    expect(screen.queryByText(/reproduction steps/i)).not.toBeInTheDocument()
  })

  it("shows the detail loading state while the detail is loading", () => {
    useOpsTicketMock.mockReturnValue({ data: undefined, isLoading: true })
    render(<OpsTicketsPage />)
    fireEvent.click(screen.getByText("Login fails after MFA"))
    expect(document.querySelector("svg")).toBeInTheDocument()
  })
})
