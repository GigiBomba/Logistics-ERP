import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import BlogListPage from "@/pages/public/blog-list"
import { useAuth } from "@/contexts/auth-provider"
import { createMockAuthContext } from "@/test-utils"
import { useBlogPosts, useBlogCategories } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useBlogPosts: vi.fn(),
  useBlogCategories: vi.fn(),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}))

const mockPosts = [
  {
    id: 1,
    title: "Trip Profitability: How to Calculate Profit Per Transport Job",
    slug: "how-to-calculate-trip-profitability-road-transport",
    excerpt: "Learn how to calculate trip profitability in road transport.",
    author_name: "Operion Team",
    category: "Profitability & Transport Finance",
    tags: ["trip-profitability"],
    reading_time_minutes: 8,
    published_at: "2026-07-12T10:00:00Z",
  },
  {
    id: 2,
    title: "Preventive Maintenance Schedule: Reduce Fleet Downtime",
    slug: "preventive-maintenance-scheduling-small-truck-fleets",
    excerpt: "Build a preventive maintenance schedule for small truck fleets.",
    author_name: "Operion Team",
    category: "Fleet Management",
    tags: ["preventive-maintenance"],
    reading_time_minutes: 6,
    published_at: "2026-06-13T10:00:00Z",
  },
]

const refetch = vi.fn()

describe("BlogListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ isAdmin: false }))
    vi.mocked(useBlogPosts).mockReturnValue({
      data: { items: mockPosts, total: 2 },
      isLoading: false,
      isError: false,
      refetch,
    } as any)
    vi.mocked(useBlogCategories).mockReturnValue({ data: [], isLoading: false } as any)
  })

  it("renders Blog heading", () => {
    render(<BlogListPage />)
    expect(screen.getByText("Blog")).toBeInTheDocument()
  })

  it("renders categories label", () => {
    render(<BlogListPage />)
    expect(screen.getByText("Categories:")).toBeInTheDocument()
  })

  it("renders All button with post count from API data", () => {
    render(<BlogListPage />)
    expect(screen.getByRole("button", { name: "All (2)" })).toBeInTheDocument()
  })

  it("renders category filter buttons with counts derived from posts", () => {
    render(<BlogListPage />)
    expect(
      screen.getByRole("button", { name: "Profitability & Transport Finance (1)" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Fleet Management (1)" })
    ).toBeInTheDocument()
  })

  it("renders blog post cards from API data", () => {
    render(<BlogListPage />)
    expect(
      screen.getByText("Trip Profitability: How to Calculate Profit Per Transport Job")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Preventive Maintenance Schedule: Reduce Fleet Downtime")
    ).toBeInTheDocument()
  })

  it("does not render admin section when not admin", () => {
    render(<BlogListPage />)
    expect(screen.queryByText("Admin mode")).not.toBeInTheDocument()
    expect(screen.queryByText("New Article")).not.toBeInTheDocument()
  })

  it("renders page description", () => {
    render(<BlogListPage />)
    expect(
      screen.getByText(/Insights, updates, and practical tips/)
    ).toBeInTheDocument()
  })

  it("shows an empty state when the API returns no posts (no invented articles)", () => {
    vi.mocked(useBlogPosts).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      refetch,
    } as any)
    render(<BlogListPage />)
    expect(screen.getByText("No articles published yet")).toBeInTheDocument()
    expect(
      screen.queryByText("Trip Profitability: How to Calculate Profit Per Transport Job")
    ).not.toBeInTheDocument()
  })

  it("shows loading skeletons while fetching", () => {
    vi.mocked(useBlogPosts).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch,
    } as any)
    render(<BlogListPage />)
    expect(screen.queryByText("Categories:")).not.toBeInTheDocument()
    expect(screen.queryByText("No articles published yet")).not.toBeInTheDocument()
    expect(screen.getByLabelText("Loading articles")).toBeInTheDocument()
  })

  it("shows an error state with retry when the request fails", () => {
    vi.mocked(useBlogPosts).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    } as any)
    render(<BlogListPage />)
    expect(screen.getByText("Failed to load articles")).toBeInTheDocument()
    const retry = screen.getByRole("button", { name: "Try again" })
    fireEvent.click(retry)
    expect(refetch).toHaveBeenCalled()
  })
})
