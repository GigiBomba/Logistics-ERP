import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import OpsGuardrailsPage from "@/pages/admin/ops/guardrails"

const { useOpsGuardrailsMock, useOpsResolveGuardrailMock } = vi.hoisted(() => ({
  useOpsGuardrailsMock: vi.fn(),
  useOpsResolveGuardrailMock: vi.fn(),
}))

vi.mock("@/services/queries", () => ({
  useOpsGuardrails: useOpsGuardrailsMock,
  useOpsResolveGuardrail: useOpsResolveGuardrailMock,
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

const violation = {
  id: 1,
  guardrail_id: "GR-7",
  severity: "hard_block",
  diff_excerpt: "-console.log(secret)\n+delete secret",
  issue_id: "TKT-9",
  resolved: false,
}

describe("OpsGuardrailsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useOpsGuardrailsMock.mockReturnValue({ data: [violation], isLoading: false, isError: false })
    useOpsResolveGuardrailMock.mockReturnValue({ mutate: vi.fn(), isPending: false })
  })

  it("shows a loading spinner while loading", () => {
    useOpsGuardrailsMock.mockReturnValue({ data: undefined, isLoading: true, isError: false })
    render(<OpsGuardrailsPage />)
    expect(document.querySelector("svg")).toBeInTheDocument()
  })

  it("shows an error state when loading fails", () => {
    useOpsGuardrailsMock.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    render(<OpsGuardrailsPage />)
    expect(screen.getByText(/failed to load guardrail violations/i)).toBeInTheDocument()
  })

  it("shows an empty state when there are no violations", () => {
    useOpsGuardrailsMock.mockReturnValue({ data: [], isLoading: false, isError: false })
    render(<OpsGuardrailsPage />)
    expect(screen.getByText(/no violations/i)).toBeInTheDocument()
  })

  it("renders violation rows with severity and status badges", () => {
    render(<OpsGuardrailsPage />)
    expect(screen.getByText("GR-7")).toBeInTheDocument()
    expect(screen.getByText("Hard block")).toBeInTheDocument()
    expect(screen.getByText("TKT-9")).toBeInTheDocument()
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("expands the diff excerpt on click", () => {
    render(<OpsGuardrailsPage />)
    expect(screen.queryByText(/\+delete secret/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText("-console.log(secret)"))
    expect(screen.getByText(/\+delete secret/i)).toBeInTheDocument()
  })

  it("resolves a violation", () => {
    const mutate = vi.fn()
    useOpsResolveGuardrailMock.mockReturnValue({ mutate, isPending: false })
    render(<OpsGuardrailsPage />)
    fireEvent.click(screen.getByRole("button", { name: /Resolve/i }))
    expect(mutate).toHaveBeenCalledWith(1)
  })

  it("shows a resolved badge and no resolve button when already resolved", () => {
    useOpsGuardrailsMock.mockReturnValue({
      data: [{ ...violation, resolved: true }],
      isLoading: false,
      isError: false,
    })
    render(<OpsGuardrailsPage />)
    expect(screen.getByText("Resolved")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Resolve/i })).not.toBeInTheDocument()
  })
})
