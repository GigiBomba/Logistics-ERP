import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import BlogArticlePage from "@/pages/public/blog-article"
import { useAuth } from "@/contexts/auth-provider"
import { useParams } from "react-router"

vi.mock("@/services/queries", () => ({
  useBlogPost: vi.fn(() => ({ isLoading: false })),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    article: ({ children, ...props }: any) => <article {...props}>{children}</article>,
  },
}))

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router")
  return {
    ...(actual as object),
    useParams: vi.fn(() => ({ slug: "how-to-calculate-trip-profitability-road-transport" })),
  }
})

describe("BlogArticlePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue({ isAdmin: false })
    vi.mocked(useParams).mockReturnValue({ slug: "how-to-calculate-trip-profitability-road-transport" })
  })

  it("renders article title", () => {
    render(<BlogArticlePage />)
    expect(
      screen.getByText("Trip Profitability: How to Calculate Profit Per Transport Job")
    ).toBeInTheDocument()
  })

  it("renders breadcrumb link back to blog", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("Back to all articles")).toBeInTheDocument()
  })

  it("shows reading time", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("8 min read")).toBeInTheDocument()
  })

  it("renders tags", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("trip-profitability")).toBeInTheDocument()
    expect(screen.getByText("cost-calculation")).toBeInTheDocument()
    expect(screen.getByText("transport-finance")).toBeInTheDocument()
  })

  it("shows author info", () => {
    render(<BlogArticlePage />)
    const authorNames = screen.getAllByText("Operion Team")
    expect(authorNames.length).toBeGreaterThanOrEqual(1)
  })

  it("renders category badge", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("Profitability & Transport Finance")).toBeInTheDocument()
  })
})

describe("BlogArticlePage not found", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue({ isAdmin: false })
    vi.mocked(useParams).mockReturnValue({ slug: "non-existent-article" })
  })

  it("shows article not found for invalid slug", () => {
    render(<BlogArticlePage />)
    const notFoundTexts = screen.getAllByText("Article Not Found")
    expect(notFoundTexts.length).toBeGreaterThanOrEqual(1)
    expect(
      screen.getByText("The article you are looking for does not exist or may have been removed.")
    ).toBeInTheDocument()
    expect(screen.getByText("Back to Blog")).toBeInTheDocument()
  })
})
