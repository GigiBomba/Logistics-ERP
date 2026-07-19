import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@/test-utils"
import BlogCategoryPage from "@/pages/public/blog-category"

vi.mock("@/services/queries", () => ({
  useBlogPosts: vi.fn(() => ({ isLoading: false })),
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
