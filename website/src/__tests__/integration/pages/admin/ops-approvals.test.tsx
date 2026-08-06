import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import OpsApprovalsPage from "@/pages/admin/ops/approvals"

const { useOpsApprovalsMock, useOpsHandleApprovalMock } = vi.hoisted(() => ({
  useOpsApprovalsMock: vi.fn(),
  useOpsHandleApprovalMock: vi.fn(),
}))

vi.mock("@/services/queries", () => ({
  useOpsApprovals: useOpsApprovalsMock,
  useOpsHandleApproval: useOpsHandleApprovalMock,
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

const approvalItem = {
  issue_id: "ISSUE-42",
  summary: "Add rate-limit to auth",
  risk_tier: "high",
  status: "pending",
  has_elevated_scrutiny: true,
  files_changed: 3,
  tests_passed: 12,
  invariants_passed: 5,
}

function mockData(data: unknown, isLoading = false, isError = false) {
  useOpsApprovalsMock.mockReturnValue({ data, isLoading, isError })
}

function mockMutation() {
  const mutate = vi.fn()
  useOpsHandleApprovalMock.mockReturnValue({ mutate, isPending: false })
  return mutate
}

describe("OpsApprovalsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockData([approvalItem])
    mockMutation()
  })

  it("shows a loading spinner while loading", () => {
    mockData(undefined, true)
    render(<OpsApprovalsPage />)
    expect(document.querySelector("svg")).toBeInTheDocument()
  })

  it("shows an error state when loading fails", () => {
    mockData(undefined, false, true)
    render(<OpsApprovalsPage />)
    expect(screen.getByText(/failed to load approvals/i)).toBeInTheDocument()
  })

  it("shows an empty state when there are no approvals", () => {
    mockData([])
    render(<OpsApprovalsPage />)
    expect(screen.getByText(/no pending approvals/i)).toBeInTheDocument()
  })

  it("renders approval cards with metadata", () => {
    render(<OpsApprovalsPage />)
    expect(screen.getByText("Add rate-limit to auth")).toBeInTheDocument()
    expect(screen.getByText("ISSUE-42")).toBeInTheDocument()
    expect(screen.getByText("high")).toBeInTheDocument()
    expect(screen.getByText(/elevated scrutiny/i)).toBeInTheDocument()
    expect(screen.getByText(/3 files/i)).toBeInTheDocument()
    expect(screen.getByText(/12 tests passed/i)).toBeInTheDocument()
  })

  it("shows the status badge when the approval is not pending", () => {
    mockData([{ ...approvalItem, status: "approved" }])
    render(<OpsApprovalsPage />)
    expect(screen.getByText("approved")).toBeInTheDocument()
  })

  it("approves via the confirmation dialog", () => {
    const mutate = mockMutation()
    render(<OpsApprovalsPage />)
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }))
    expect(screen.getByText(/approve this change/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Yes, approve/i }))
    expect(mutate).toHaveBeenCalledWith({ id: "ISSUE-42", action: "approve" })
    expect(screen.queryByText(/approve this change/i)).not.toBeInTheDocument()
  })

  it("rejects via the confirmation dialog", () => {
    const mutate = mockMutation()
    render(<OpsApprovalsPage />)
    fireEvent.click(screen.getByRole("button", { name: /Reject/i }))
    expect(screen.getByText(/reject this change/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Yes, reject/i }))
    expect(mutate).toHaveBeenCalledWith({ id: "ISSUE-42", action: "reject" })
  })

  it("cancels the confirmation dialog", () => {
    render(<OpsApprovalsPage />)
    fireEvent.click(screen.getByRole("button", { name: /Reject/i }))
    fireEvent.click(screen.getByRole("button", { name: /Cancel/i }))
    expect(screen.queryByText(/reject this change/i)).not.toBeInTheDocument()
  })

  it("asks a question directly without confirmation", () => {
    const mutate = mockMutation()
    render(<OpsApprovalsPage />)
    fireEvent.click(screen.getByRole("button", { name: /Ask a question/i }))
    expect(mutate).toHaveBeenCalledWith({ id: "ISSUE-42", action: "ask_question" })
  })
})
