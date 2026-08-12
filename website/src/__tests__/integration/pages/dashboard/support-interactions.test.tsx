import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import SupportPage from "@/pages/dashboard/support"
import { useCreateTicket, useTickets, useTutorials } from "@/services/queries"
import userEvent from "@testing-library/user-event"

vi.mock("@/services/queries", () => ({
  useCreateTicket: vi.fn(),
  useTickets: vi.fn(),
  useTutorials: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div>, p: ({ children, ...props }: any) => <p {...props}>{children}</p> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const tutorial = {
  id: "t-1",
  title: "Your First Route Plan",
  slug: "your-first-route-plan",
  excerpt: "Plan your first multi-stop route.",
  category: "beginner",
  reading_time_minutes: 7,
  published_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
  content: "<p>x</p>",
}

const tickets = [
  {
    id: "t1",
    subject: "App crashes on login",
    status: "open",
    priority: "high",
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-02T00:00:00Z",
  },
  {
    id: "t2",
    subject: "Add dark mode",
    status: "resolved",
    priority: "low",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-10T00:00:00Z",
  },
]

const makeMutation = (overrides: Record<string, any> = {}) => ({
  mutate: vi.fn(),
  isPending: false,
  ...overrides,
})

describe("SupportPage — ticket submission", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation() as any)
    vi.mocked(useTickets).mockReturnValue({ data: [], isLoading: false, isError: false } as any)
    vi.mocked(useTutorials).mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() } as any)
  })

  it("submits a bug report including steps", async () => {
    const mutate = vi.fn()
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<SupportPage />)

    await user.type(screen.getByPlaceholderText(/brief description/i), "Login button does nothing")
    await user.type(screen.getByPlaceholderText(/what happened/i), "Clicked login and nothing happened at all")
    await user.type(screen.getByPlaceholderText(/1\. go to/i), "1. Open app\n2. Click login")
    await user.click(screen.getByRole("button", { name: /submit bug report/i }))

    expect(mutate).toHaveBeenCalledWith({
      subject: "[Bug] Login button does nothing",
      description:
        "Clicked login and nothing happened at all\n\nSteps to reproduce:\n1. Open app\n2. Click login",
    })
  })

  it("submits a bug report without steps", async () => {
    const mutate = vi.fn()
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<SupportPage />)

    await user.type(screen.getByPlaceholderText(/brief description/i), "Email field too small")
    await user.type(screen.getByPlaceholderText(/what happened/i), "The email input is hard to use on mobile")
    await user.click(screen.getByRole("button", { name: /submit bug report/i }))

    expect(mutate).toHaveBeenCalledWith({
      subject: "[Bug] Email field too small",
      description: "The email input is hard to use on mobile",
    })
  })

  it("submits a feature request including use case", async () => {
    const mutate = vi.fn()
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<SupportPage />)

    await user.type(screen.getByPlaceholderText(/name your feature/i), "Bulk route export")
    await user.type(screen.getByPlaceholderText(/describe the feature/i), "Export all planned routes as CSV for offline use")
    await user.type(screen.getByPlaceholderText(/how would this/i), "I want to print routes for drivers")
    await user.click(screen.getByRole("button", { name: /submit feature request/i }))

    expect(mutate).toHaveBeenCalledWith({
      subject: "[Feature] Bulk route export",
      description:
        "Export all planned routes as CSV for offline use\n\nUse case:\nI want to print routes for drivers",
    })
  })

  it("shows validation errors for short inputs and does not submit", async () => {
    const mutate = vi.fn()
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation({ mutate }) as any)
    const user = userEvent.setup()
    render(<SupportPage />)

    await user.type(screen.getByPlaceholderText(/brief description/i), "Ab")
    await user.click(screen.getByRole("button", { name: /submit bug report/i }))

    expect(screen.getByText("Title must be at least 5 characters")).toBeInTheDocument()
    expect(screen.getByText("Please provide a detailed description")).toBeInTheDocument()
    expect(mutate).not.toHaveBeenCalled()
  })

  it("shows submitting label while pending", () => {
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation({ isPending: true }) as any)
    render(<SupportPage />)
    const buttons = screen.getAllByRole("button", { name: /submitting/i })
    expect(buttons.length).toBeGreaterThanOrEqual(1)
  })
})

describe("SupportPage — tickets tab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation() as any)
    vi.mocked(useTutorials).mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() } as any)
  })

  it("lists tickets with priority and status badges", () => {
    vi.mocked(useTickets).mockReturnValue({ data: tickets, isLoading: false, isError: false } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /my tickets/i }))
    expect(screen.getByText("App crashes on login")).toBeInTheDocument()
    expect(screen.getByText("Add dark mode")).toBeInTheDocument()
    expect(screen.getByText("high")).toBeInTheDocument()
    expect(screen.getByText("resolved")).toBeInTheDocument()
  })

  it("filters tickets by status", () => {
    vi.mocked(useTickets).mockReturnValue({ data: tickets, isLoading: false, isError: false } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /my tickets/i }))
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "open" } })
    expect(screen.getByText("App crashes on login")).toBeInTheDocument()
    expect(screen.queryByText("Add dark mode")).not.toBeInTheDocument()
  })

  it("shows the no-tickets-found empty state when the filter matches nothing", () => {
    vi.mocked(useTickets).mockReturnValue({ data: tickets, isLoading: false, isError: false } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /my tickets/i }))
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "closed" } })
    expect(screen.getByText("No tickets found")).toBeInTheDocument()
    expect(screen.getByText("No tickets match the selected filter.")).toBeInTheDocument()
  })

  it("shows the empty state when there are no tickets", () => {
    vi.mocked(useTickets).mockReturnValue({ data: [], isLoading: false, isError: false } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /my tickets/i }))
    expect(screen.getByText("No tickets yet")).toBeInTheDocument()
  })

  it("shows a loading spinner while tickets load", () => {
    vi.mocked(useTickets).mockReturnValue({ data: [], isLoading: true, isError: false } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /my tickets/i }))
    expect(screen.getByText("Ticket History")).toBeInTheDocument()
  })

  it("shows an error empty state when tickets fail to load", () => {
    vi.mocked(useTickets).mockReturnValue({ data: [], isLoading: false, isError: true } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /my tickets/i }))
    expect(screen.getByText("Failed to load tickets")).toBeInTheDocument()
  })
})

describe("SupportPage — knowledge base tab", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCreateTicket).mockReturnValue(makeMutation() as any)
    vi.mocked(useTickets).mockReturnValue({ data: [], isLoading: false, isError: false } as any)
  })

  it("renders tutorials and reading time", () => {
    vi.mocked(useTutorials).mockReturnValue({ data: [tutorial], isLoading: false, isError: false, refetch: vi.fn() } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /knowledge base/i }))
    expect(screen.getByText("Your First Route Plan")).toBeInTheDocument()
    expect(screen.getByText("7 min read")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /your first route plan/i })).toHaveAttribute("href", "/tutorials/your-first-route-plan")
  })

  it("shows tutorial loading spinner", () => {
    vi.mocked(useTutorials).mockReturnValue({ data: undefined, isLoading: true, isError: false, refetch: vi.fn() } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /knowledge base/i }))
    expect(screen.getAllByText("Knowledge Base").length).toBeGreaterThanOrEqual(1)
  })

  it("shows knowledge base error state with retry", () => {
    const refetch = vi.fn()
    vi.mocked(useTutorials).mockReturnValue({ data: undefined, isLoading: false, isError: true, refetch } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /knowledge base/i }))
    expect(screen.getByText("Failed to load the knowledge base")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /try again/i }))
    expect(refetch).toHaveBeenCalled()
  })

  it("shows knowledge base empty state", () => {
    vi.mocked(useTutorials).mockReturnValue({ data: [], isLoading: false, isError: false, refetch: vi.fn() } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /knowledge base/i }))
    expect(screen.getByText("No tutorials yet")).toBeInTheDocument()
  })

  it("expands and collapses FAQ answers", () => {
    vi.mocked(useTutorials).mockReturnValue({ data: [tutorial], isLoading: false, isError: false, refetch: vi.fn() } as any)
    render(<SupportPage />)
    fireEvent.click(screen.getByRole("tab", { name: /knowledge base/i }))

    expect(screen.queryByText(/Go to Settings > Security/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /how do i reset my password/i }))
    expect(screen.getByText(/Go to Settings > Security/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /how do i reset my password/i }))
    expect(screen.queryByText(/Go to Settings > Security/)).not.toBeInTheDocument()
  })
})
