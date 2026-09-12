import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import BlogAuthorPage from "@/pages/public/blog-author"
import { useBlogPosts, useBlogAuthor } from "@/services/queries"

vi.mock("@/services/queries", () => ({
  useBlogPosts: vi.fn(),
  useBlogAuthor: vi.fn(),
}))

const mockAuthor = {
  id: "operion-team",
  name: "Operion Team",
  role: "Transport & Logistics",
  bio: "The Operion Team writes about fleet management, transport operations, and logistics best practices. We are building a logistics ERP for transport professionals, based in Romania.",
  avatar_url: undefined as string | undefined,
}

const mockPosts = [
  {
    title: "Preventive Maintenance Guide: Keep Your Fleet on the Road",
    slug: "preventive-maintenance-guide",
    excerpt: "Keep your fleet on the road with a solid preventive maintenance plan.",
    author_name: "Operion Team",
    category: "Fleet Management",
    tags: ["fleet-management"],
    reading_time_minutes: 6,
    published_at: "2026-07-01T10:00:00Z",
  },
  {
    title: "Tire Management and Its Impact on Operating Costs",
    slug: "tire-management-operating-costs",
    excerpt: "How proactive tire management lowers your operating costs.",
    author_name: "Operion Team",
    category: "Fleet Management",
    tags: ["fleet-management"],
    reading_time_minutes: 5,
    published_at: "2026-06-20T10:00:00Z",
  },
  {
    title: "Route Optimization Basics for Small Fleets",
    slug: "route-optimization-basics",
    excerpt: "A practical introduction to route optimization.",
    author_name: "Operion Team",
    category: "Route Planning",
    tags: ["route-planning"],
    reading_time_minutes: 7,
    published_at: "2026-06-10T10:00:00Z",
  },
  {
    title: "Fuel Cost Reduction Strategies",
    slug: "fuel-cost-reduction",
    excerpt: "Reduce fuel spend without sacrificing service levels.",
    author_name: "Operion Team",
    category: "Profitability & Transport Finance",
    tags: ["fuel"],
    reading_time_minutes: 8,
    published_at: "2026-05-28T10:00:00Z",
  },
  {
    title: "Dispatch Automation Explained",
    slug: "dispatch-automation-explained",
    excerpt: "How automated dispatch improves coordination.",
    author_name: "Operion Team",
    category: "Dispatching",
    tags: ["dispatch"],
    reading_time_minutes: 6,
    published_at: "2026-05-15T10:00:00Z",
  },
  {
    title: "Driver Compliance Checklist",
    slug: "driver-compliance-checklist",
    excerpt: "Keep drivers compliant with a simple checklist.",
    author_name: "Operion Team",
    category: "Compliance",
    tags: ["compliance"],
    reading_time_minutes: 4,
    published_at: "2026-05-01T10:00:00Z",
  },
  {
    title: "Telematics Data You Should Track",
    slug: "telematics-data-to-track",
    excerpt: "The telematics metrics that matter most.",
    author_name: "Operion Team",
    category: "Fleet Management",
    tags: ["telematics"],
    reading_time_minutes: 5,
    published_at: "2026-04-18T10:00:00Z",
  },
]

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

describe("BlogAuthorPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseParams.mockReturnValue({ authorId: "operion-team" })
    mockUseSearchParams.mockReturnValue([new URLSearchParams(), vi.fn()])
    vi.mocked(useBlogPosts).mockReturnValue({
      data: { items: mockPosts, total: mockPosts.length },
      isLoading: false,
    } as any)
    vi.mocked(useBlogAuthor).mockImplementation((id: string | number | undefined) =>
      (id === "operion-team"
        ? { data: mockAuthor, isLoading: false }
        : { data: undefined, isLoading: false }) as any
    )
  })

  it("renders the author name in page title and profile", () => {
    render(<BlogAuthorPage />)
    const authorNames = screen.getAllByText("Operion Team")
    expect(authorNames.length).toBeGreaterThanOrEqual(2)
  })

  it("renders the author role", () => {
    render(<BlogAuthorPage />)
    expect(screen.getByText("Transport & Logistics at Operion")).toBeInTheDocument()
  })

  it("renders the author bio", () => {
    render(<BlogAuthorPage />)
    expect(
      screen.getByText(
        "The Operion Team writes about fleet management, transport operations, and logistics best practices. We are building a logistics ERP for transport professionals, based in Romania."
      )
    ).toBeInTheDocument()
  })

  it("renders the author avatar placeholder", () => {
    render(<BlogAuthorPage />)
    const avatar = document.querySelector(".rounded-full.bg-accent")
    expect(avatar).toBeInTheDocument()
  })

  it("renders article count", () => {
    render(<BlogAuthorPage />)
    expect(screen.getByText(/7 articles/)).toBeInTheDocument()
  })

  it("renders 'All articles' back link pointing to /blog", () => {
    render(<BlogAuthorPage />)
    const link = screen.getByText("All articles")
    expect(link.closest("a")).toHaveAttribute("href", "/blog")
  })

  it("renders blog post cards for the author", () => {
    render(<BlogAuthorPage />)
    expect(
      screen.getByText("Preventive Maintenance Guide: Keep Your Fleet on the Road")
    ).toBeInTheDocument()
  })

  it("renders post categories on cards", () => {
    render(<BlogAuthorPage />)
    const fleetManagementLabels = screen.getAllByText("Fleet Management")
    expect(fleetManagementLabels.length).toBeGreaterThanOrEqual(1)
  })

  it("shows author not found for invalid authorId", () => {
    mockUseParams.mockReturnValue({ authorId: "nonexistent" })
    render(<BlogAuthorPage />)
    expect(screen.getByText("Author Not Found")).toBeInTheDocument()
    expect(screen.getByText("This author does not exist.")).toBeInTheDocument()
  })

  it("shows back to blog link when author not found", () => {
    mockUseParams.mockReturnValue({ authorId: "nonexistent" })
    render(<BlogAuthorPage />)
    const link = screen.getByText("Back to Blog")
    expect(link.closest("a")).toHaveAttribute("href", "/blog")
  })
})
