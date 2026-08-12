import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import OpsDashboardsPage from "@/pages/admin/ops/dashboards"

const { useOpsDashboardMock } = vi.hoisted(() => ({ useOpsDashboardMock: vi.fn() }))

vi.mock("@/services/queries", () => ({
  useOpsDashboard: useOpsDashboardMock,
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

describe("OpsDashboardsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useOpsDashboardMock.mockReturnValue({
      data: { unresolved: 3, pending_approvals: 2, patch_success_rate: 98, critical_escalations: 0 },
      isLoading: false,
      isError: false,
    })
  })

  it("shows a loading spinner while loading", () => {
    useOpsDashboardMock.mockReturnValue({ data: undefined, isLoading: true, isError: false })
    render(<OpsDashboardsPage />)
    expect(document.querySelector("svg")).toBeInTheDocument()
  })

  it("shows an error state when loading fails", () => {
    useOpsDashboardMock.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    render(<OpsDashboardsPage />)
    expect(screen.getByText(/failed to load dashboard data/i)).toBeInTheDocument()
  })

  it("renders the summary cards with data", () => {
    render(<OpsDashboardsPage />)
    expect(screen.getByText("3")).toBeInTheDocument()
    expect(screen.getByText("Unresolved")).toBeInTheDocument()
    expect(screen.getByText("98%")).toBeInTheDocument()
    expect(screen.getByText("Patch success rate")).toBeInTheDocument()
  })

  it("renders fallback dashes when the summary is missing", () => {
    useOpsDashboardMock.mockReturnValue({ data: undefined, isLoading: false, isError: false })
    render(<OpsDashboardsPage />)
    expect(screen.getAllByText("—").length).toBeGreaterThan(0)
  })

  it("renders the static health panels", () => {
    render(<OpsDashboardsPage />)
    expect(screen.getByText(/Support health/i)).toBeInTheDocument()
    expect(screen.getByText(/Pipeline funnel/i)).toBeInTheDocument()
    expect(screen.getByText(/Guardrail activity/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Cost/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Dependency health/i)).toBeInTheDocument()
  })
})
