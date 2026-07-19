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

  it("renders category filter tabs with All and categories", () => {
    render(<BlogListPage />)
    expect(screen.getByRole("button", { name: /All/i })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Profitability & Transport Finance/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Fleet Management/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Dispatching/i })
    ).toBeInTheDocument()
  })

  it("renders blog post cards", () => {
    render(<BlogListPage />)
    expect(
      screen.getByText("Trip Profitability: How to Calculate Profit Per Transport Job")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Fuel Cost Management: Strategies for Small Transport Fleets")
    ).toBeInTheDocument()
  })

  it("does not render admin section when not admin", () => {
    render(<BlogListPage />)
    expect(screen.queryByText("Admin mode")).not.toBeInTheDocument()
    expect(screen.queryByText("New Article")).not.toBeInTheDocument()
  })
})
