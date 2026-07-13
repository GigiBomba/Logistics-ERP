import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import BlogListPage from "@/pages/public/blog-list"
import { useAuth } from "@/contexts/auth-provider"

vi.mock("@/services/queries", () => ({
  useBlogPosts: vi.fn(() => ({ isLoading: false })),
  useBlogCategories: vi.fn(() => ({ isLoading: false })),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}))

describe("BlogListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue({ isAdmin: false })
  })

  it("renders Blog heading", () => {
    render(<BlogListPage />)
    expect(screen.getByText("Blog")).toBeInTheDocument()
  })

  it("renders search input with correct placeholder", () => {
    render(<BlogListPage />)
    expect(
      screen.getByPlaceholderText("Search articles...")
    ).toBeInTheDocument()
  })

  it("renders category filter tabs with All and all categories", () => {
    render(<BlogListPage />)
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Product Updates" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Engineering" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Logistics" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Tutorials" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Company News" })
    ).toBeInTheDocument()
  })

  it("renders blog post cards with mock article titles", () => {
    render(<BlogListPage />)
    // Title appears in both featured post and card, so use getAllByText
    const titles = screen.getAllByText("Getting Started with Operion")
    expect(titles.length).toBeGreaterThanOrEqual(1)
    expect(
      screen.getByText("How Real-Time Traffic Data Cuts Delivery Times by 23%")
    ).toBeInTheDocument()
  })

  it("renders the article count", () => {
    render(<BlogListPage />)
    expect(screen.getByText(/articles?/)).toBeInTheDocument()
  })

  it("does not render admin section when not admin", () => {
    render(<BlogListPage />)
    expect(screen.queryByText("Admin mode")).not.toBeInTheDocument()
    expect(screen.queryByText("New Article")).not.toBeInTheDocument()
  })

  it("renders featured post section", () => {
    render(<BlogListPage />)
    expect(screen.getByText("Featured")).toBeInTheDocument()
  })
})
