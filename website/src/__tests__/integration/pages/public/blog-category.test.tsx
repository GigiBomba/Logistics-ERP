import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import BlogCategoryPage from "@/pages/public/blog-category"
import { useBlogPosts } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useBlogPosts: vi.fn(),
}))

const fleetPosts = [
  {
    title: "Preventive Maintenance Scheduling for Small Truck Fleets",
    slug: "preventive-maintenance-scheduling-small-truck-fleets",
    excerpt: "Build a preventive maintenance schedule for small truck fleets.",
    author_name: "Operion Team",
    category: "Fleet Management",
    tags: ["preventive-maintenance"],
    reading_time_minutes: 6,
    published_at: "2026-06-13T10:00:00Z",
  },
  {
    title: "Tire Management and Its Impact on Operating Costs",
    slug: "tire-management-operating-costs",
    excerpt: "How proactive tire management lowers operating costs.",
    author_name: "Operion Team",
    category: "Fleet Management",
    tags: ["tires"],
    reading_time_minutes: 5,
    published_at: "2026-05-20T10:00:00Z",
  },
]

const financePosts = Array.from({ length: 9 }, (_, i) => ({
  title: `Transport Finance Article ${i + 1}`,
  slug: `transport-finance-article-${i + 1}`,
  excerpt: `Insight number ${i + 1} on transport finance.`,
  author_name: "Operion Team",
  category: "Profitability & Transport Finance",
  tags: ["finance"],
  reading_time_minutes: 6,
  published_at: "2026-04-01T10:00:00Z",
}))

vi.mock("motion/react", () => ({
  motion: new Proxy(
    {},
    {
      get: () => (props: any) => props?.children ?? null,
    }
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const mockUseParams = vi.fn()
const mockUseSearchParams = vi.fn()

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router")
  return {
    ...(actual as object),
    useParams: () => mockUseParams(),
    useSearchParams: () => mockUseSearchParams(),
  }
})

describe("BlogCategoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseSearchParams.mockReturnValue([new URLSearchParams(), vi.fn()])
    vi.mocked(useBlogPosts).mockImplementation((params?: any) => {
      if (params?.category === "fleet-management") {
        return { data: { items: fleetPosts, total: 2 }, isLoading: false } as any
      }
      if (params?.category === "profitability-&-transport-finance") {
        return { data: { items: financePosts, total: 10 }, isLoading: false } as any
      }
      return { data: { items: [], total: 0 }, isLoading: false } as any
    })
  })

  it("renders the category page title for fleet-management", () => {
    mockUseParams.mockReturnValue({ category: "fleet-management" })
    render(<BlogCategoryPage />)
    const fleetMgmtElements = screen.getAllByText("Fleet Management")
    expect(fleetMgmtElements.length).toBeGreaterThanOrEqual(1)
  })

  it("renders the search input with placeholder", () => {
    mockUseParams.mockReturnValue({ category: "fleet-management" })
    render(<BlogCategoryPage />)
    expect(screen.getByPlaceholderText("Search articles...")).toBeInTheDocument()
  })

  it("renders article count for fleet-management", () => {
    mockUseParams.mockReturnValue({ category: "fleet-management" })
    render(<BlogCategoryPage />)
    expect(screen.getByText(/2 articles/)).toBeInTheDocument()
  })

  it("renders 'All categories' back link pointing to /blog", () => {
    mockUseParams.mockReturnValue({ category: "fleet-management" })
    render(<BlogCategoryPage />)
    const link = screen.getByText("All categories")
    expect(link.closest("a")).toHaveAttribute("href", "/blog")
  })

  it("renders blog post cards for fleet-management category", () => {
    mockUseParams.mockReturnValue({ category: "fleet-management" })
    render(<BlogCategoryPage />)
    expect(
      screen.getByText("Preventive Maintenance Scheduling for Small Truck Fleets")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Tire Management and Its Impact on Operating Costs")
    ).toBeInTheDocument()
  })

  it("shows no articles found for unknown category", () => {
    mockUseParams.mockReturnValue({ category: "unknown-category" })
    render(<BlogCategoryPage />)
    expect(screen.getByText("No articles found")).toBeInTheDocument()
  })

  it("renders pagination for category with 10 posts", () => {
    // Slug must match the actual character-level conversion
    mockUseParams.mockReturnValue({ category: "profitability-&-transport-finance" })
    render(<BlogCategoryPage />)
    expect(screen.getByText("1")).toBeInTheDocument()
    expect(screen.getByText("2")).toBeInTheDocument()
  })
})
