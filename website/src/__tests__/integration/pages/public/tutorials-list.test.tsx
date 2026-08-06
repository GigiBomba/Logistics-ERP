import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import userEvent from "@testing-library/user-event"
import TutorialsListPage from "@/pages/public/tutorials-list"
import { useTutorials } from "@/services/queries"

const mockTutorials = [
  { title: "Route Planning Basics", slug: "route-planning", category: "Fleet Manager", difficulty: "Beginner", reading_time_minutes: 12, published_at: "2026-01-15", excerpt: "Plan efficient routes for your fleet." },
  { title: "Dispatch Guide", slug: "dispatch-guide", category: "Dispatcher", difficulty: "Intermediate", reading_time_minutes: 8, published_at: "2026-02-01", excerpt: "Dispatch drivers and track deliveries." },
  { title: "Using AI Assistant", slug: "ai-assistant", category: "AI Assistant", difficulty: "Advanced", reading_time_minutes: 15, published_at: "2026-03-01", excerpt: "Automate workflows with the AI assistant." },
]

vi.mock("@/services/queries", () => ({
  useTutorials: vi.fn(),
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

describe("TutorialsListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTutorials).mockReturnValue({
      isLoading: false,
      data: mockTutorials,
    } as any)
  })

  it("renders 'Tutorials' heading", () => {
    render(<TutorialsListPage />)
    expect(screen.getByText("Tutorials")).toBeInTheDocument()
  })

  it("shows search input", () => {
    render(<TutorialsListPage />)
    expect(screen.getByPlaceholderText("Search tutorials...")).toBeInTheDocument()
  })

  it("shows category filter tabs", () => {
    render(<TutorialsListPage />)
    expect(screen.getByText("All")).toBeInTheDocument()
    expect(screen.getAllByText("Beginner").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Intermediate").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Advanced").length).toBeGreaterThanOrEqual(1)
  })

  it("renders tutorial cards with category badges", () => {
    render(<TutorialsListPage />)
    expect(screen.getAllByText("Fleet Manager").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Dispatcher").length).toBeGreaterThanOrEqual(1)
  })

  it("shows difficulty level badges", () => {
    render(<TutorialsListPage />)
    expect(screen.getAllByText("Beginner").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Intermediate").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("Advanced").length).toBeGreaterThanOrEqual(1)
  })

  it("shows reading time", () => {
    render(<TutorialsListPage />)
    expect(screen.getAllByText(/12 min read/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/8 min read/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/15 min read/).length).toBeGreaterThanOrEqual(1)
  })

  it("shows tutorial count", () => {
    render(<TutorialsListPage />)
    expect(screen.getByText((content) => content.includes("3") && content.includes("tutorial"))).toBeInTheDocument()
  })

  it("filters tutorials by clicking a category tag", async () => {
    const user = userEvent.setup()
    render(<TutorialsListPage />, { initialEntries: ["/tutorials"] })
    await user.click(screen.getByRole("button", { name: /^dispatcher$/i }))
    expect(screen.getByText("Dispatch Guide")).toBeInTheDocument()
    expect(screen.queryByText("Route Planning Basics")).not.toBeInTheDocument()
  })

  it("filters tutorials by search query", async () => {
    const user = userEvent.setup()
    render(<TutorialsListPage />, { initialEntries: ["/tutorials"] })
    const search = screen.getByPlaceholderText("Search tutorials...")
    await user.type(search, "ai")
    expect(screen.getByText("Using AI Assistant")).toBeInTheDocument()
    expect(screen.queryByText("Route Planning Basics")).not.toBeInTheDocument()
  })

  it("clears the search filter", async () => {
    const user = userEvent.setup()
    render(<TutorialsListPage />, { initialEntries: ["/tutorials"] })
    const search = screen.getByPlaceholderText("Search tutorials...")
    await user.type(search, "zzz-no-results")
    expect(screen.getByText("No tutorials found")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /clear all filters/i }))
    expect(screen.getByText("Route Planning Basics")).toBeInTheDocument()
  })

  it("shows the loading skeleton while fetching", () => {
    vi.mocked(useTutorials).mockReturnValue({ isLoading: true, data: undefined } as any)
    render(<TutorialsListPage />)
    expect(document.querySelector(".animate-pulse")).not.toBeNull()
  })

  it("reads the category filter from the URL", () => {
    render(<TutorialsListPage />, { initialEntries: ["/tutorials?category=Dispatcher"] })
    expect(screen.getByText("Dispatch Guide")).toBeInTheDocument()
    expect(screen.queryByText("Route Planning Basics")).not.toBeInTheDocument()
  })

  it("paginates tutorials when there are more than the page size", () => {
    const manyTutorials = Array.from({ length: 20 }, (_, i) => ({
      title: `Tutorial ${i + 1}`,
      slug: `tutorial-${i + 1}`,
      category: "All",
      difficulty: "Beginner",
      reading_time_minutes: 5,
      published_at: "2026-01-01",
      excerpt: `Excerpt ${i + 1}`,
    }))
    vi.mocked(useTutorials).mockReturnValue({ isLoading: false, data: manyTutorials } as any)
    render(<TutorialsListPage />, { initialEntries: ["/tutorials"] })
    expect(screen.getByText("Tutorial 1")).toBeInTheDocument()
    expect(screen.queryByText("Tutorial 10")).not.toBeInTheDocument()
    expect(screen.getByText("Tutorial 9")).toBeInTheDocument()
  })

  it("handles keyboard Enter on a filter tag", async () => {
    const user = userEvent.setup()
    render(<TutorialsListPage />, { initialEntries: ["/tutorials"] })
    const dispatcherTag = screen.getByRole("button", { name: /^dispatcher$/i })
    dispatcherTag.focus()
    await user.keyboard("{Enter}")
    expect(screen.getByText("Dispatch Guide")).toBeInTheDocument()
    expect(screen.queryByText("Route Planning Basics")).not.toBeInTheDocument()
  })
})
