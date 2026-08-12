import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import OpsKnowledgePage from "@/pages/admin/ops/knowledge"

const { useOpsKnowledgeDraftsMock, useOpsApproveKnowledgeDocMock, useOpsRejectKnowledgeDocMock } = vi.hoisted(
  () => ({
    useOpsKnowledgeDraftsMock: vi.fn(),
    useOpsApproveKnowledgeDocMock: vi.fn(),
    useOpsRejectKnowledgeDocMock: vi.fn(),
  })
)

vi.mock("@/services/queries", () => ({
  useOpsKnowledgeDrafts: useOpsKnowledgeDraftsMock,
  useOpsApproveKnowledgeDoc: useOpsApproveKnowledgeDocMock,
  useOpsRejectKnowledgeDoc: useOpsRejectKnowledgeDocMock,
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

const draft = {
  id: 5,
  doc_id: "DOC-101",
  corpus: "internal",
  status: "pending",
  section: "Dispatch",
  content: "Draft body content here.",
  last_updated: "2026-05-01T10:00:00Z",
}

describe("OpsKnowledgePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useOpsKnowledgeDraftsMock.mockReturnValue({ data: [draft], isLoading: false, isError: false })
    useOpsApproveKnowledgeDocMock.mockReturnValue({ mutate: vi.fn(), isPending: false })
    useOpsRejectKnowledgeDocMock.mockReturnValue({ mutate: vi.fn(), isPending: false })
  })

  it("shows a loading spinner while loading", () => {
    useOpsKnowledgeDraftsMock.mockReturnValue({ data: undefined, isLoading: true, isError: false })
    render(<OpsKnowledgePage />)
    expect(document.querySelector("svg")).toBeInTheDocument()
  })

  it("shows an error state when loading fails", () => {
    useOpsKnowledgeDraftsMock.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    render(<OpsKnowledgePage />)
    expect(screen.getByText(/failed to load knowledge drafts/i)).toBeInTheDocument()
  })

  it("shows an empty state when there are no drafts", () => {
    useOpsKnowledgeDraftsMock.mockReturnValue({ data: [], isLoading: false, isError: false })
    render(<OpsKnowledgePage />)
    expect(screen.getByText(/no pending drafts/i)).toBeInTheDocument()
  })

  it("renders draft cards with corpus and status badges", () => {
    render(<OpsKnowledgePage />)
    expect(screen.getByText("DOC-101")).toBeInTheDocument()
    expect(screen.getByText("internal")).toBeInTheDocument()
    expect(screen.getByText("pending")).toBeInTheDocument()
    expect(screen.getByText(/Section: Dispatch/)).toBeInTheDocument()
  })

  it("expands a draft to show its content", () => {
    render(<OpsKnowledgePage />)
    expect(screen.queryByText("Draft body content here.")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Show more/i }))
    expect(screen.getByText("Draft body content here.")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Show less/i }))
    expect(screen.queryByText("Draft body content here.")).not.toBeInTheDocument()
  })

  it("approves a pending draft", () => {
    const mutate = vi.fn()
    useOpsApproveKnowledgeDocMock.mockReturnValue({ mutate, isPending: false })
    render(<OpsKnowledgePage />)
    fireEvent.click(screen.getByRole("button", { name: /Approve/i }))
    expect(mutate).toHaveBeenCalledWith("5")
  })

  it("rejects a pending draft", () => {
    const mutate = vi.fn()
    useOpsRejectKnowledgeDocMock.mockReturnValue({ mutate, isPending: false })
    render(<OpsKnowledgePage />)
    fireEvent.click(screen.getByRole("button", { name: /Reject/i }))
    expect(mutate).toHaveBeenCalledWith("5")
  })

  it("hides approve/reject buttons for non-pending drafts", () => {
    useOpsKnowledgeDraftsMock.mockReturnValue({
      data: [{ ...draft, status: "approved" }],
      isLoading: false,
      isError: false,
    })
    render(<OpsKnowledgePage />)
    expect(screen.getByText("approved")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument()
  })
})
