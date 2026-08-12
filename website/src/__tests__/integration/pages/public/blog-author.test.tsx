import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import BlogAuthorPage from "@/pages/public/blog-author"

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

describe("BlogAuthorPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseParams.mockReturnValue({ authorId: "operion-team" })
    mockUseSearchParams.mockReturnValue([new URLSearchParams(), vi.fn()])
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
