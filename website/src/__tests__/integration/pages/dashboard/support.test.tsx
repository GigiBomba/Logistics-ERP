import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import SupportPage from "@/pages/dashboard/support"
import { useCreateTicket } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useCreateTicket: vi.fn(),
  useTickets: vi.fn(() => ({ data: [], isLoading: false })),
  useTutorials: vi.fn(() => ({
    data: [
      {
        id: "t-1",
        title: "Your First Route Plan",
        slug: "your-first-route-plan",
        excerpt: "Plan your first multi-stop route.",
        category: "beginner",
        reading_time_minutes: 7,
        published_at: "2026-07-01T00:00:00Z",
        updated_at: "2026-07-01T00:00:00Z",
        content: "<p>x</p>",
      },
    ],
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  })),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe("SupportPage", () => {
  const mockMutate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCreateTicket).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    } as any)
  })

  it("renders both forms", () => {
    render(<SupportPage />)
    expect(screen.getByText("Support")).toBeInTheDocument()
    expect(screen.getByText("Report a Bug")).toBeInTheDocument()
    expect(screen.getByText("Request a Feature")).toBeInTheDocument()
  })

  it("renders contact information", () => {
    render(<SupportPage />)
    expect(screen.getByText("Contact Information")).toBeInTheDocument()
    expect(screen.getByText("support@operionerp.xyz")).toBeInTheDocument()
  })

  it("shows ticket history as empty state", () => {
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /my tickets/i }))
    expect(screen.getByText("Ticket History")).toBeInTheDocument()
    expect(screen.getByText(/No tickets/i)).toBeInTheDocument()
  })

  it("renders real tutorials in the knowledge base tab", () => {
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /knowledge base/i }))
    expect(screen.getByText("Your First Route Plan")).toBeInTheDocument()
    expect(screen.getByText("7 min read")).toBeInTheDocument()
  })

  it("renders bug form fields", () => {
    render(<SupportPage />)
    expect(screen.getByPlaceholderText(/brief description/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/what happened/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/1\. go to/i)).toBeInTheDocument()
  })

  it("renders feature form fields", () => {
    render(<SupportPage />)
    expect(screen.getByPlaceholderText(/name your feature/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/describe the feature/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/how would this/i)).toBeInTheDocument()
  })
})

describe("SupportPage form validation", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCreateTicket).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as any)
  })

  it("renders submit buttons on both forms", () => {
    render(<SupportPage />)
    const buttons = screen.getAllByRole("button", { name: /submit/i })
    expect(buttons.length).toBe(2)
  })
})
