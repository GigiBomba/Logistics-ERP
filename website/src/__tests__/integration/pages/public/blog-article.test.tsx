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
  },
}))

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router")
  return {
    ...(actual as object),
    useParams: vi.fn(() => ({ slug: "getting-started-with-operion" })),
  }
})

describe("BlogArticlePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue({ isAdmin: false })
    vi.mocked(useParams).mockReturnValue({ slug: "getting-started-with-operion" })
  })

  it("renders article title", () => {
    render(<BlogArticlePage />)
    expect(
      screen.getByText("Getting Started with Operion")
    ).toBeInTheDocument()
  })

  it("renders breadcrumb link back to blog", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("Back to Blog")).toBeInTheDocument()
  })

  it("shows reading time", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("8 min read")).toBeInTheDocument()
  })

  it("renders tags", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("onboarding")).toBeInTheDocument()
    expect(screen.getByText("fleet-setup")).toBeInTheDocument()
    expect(screen.getByText("dispatch")).toBeInTheDocument()
  })

  it("shows author info", () => {
    render(<BlogArticlePage />)
    const authorNames = screen.getAllByText("Sarah Chen")
    expect(authorNames.length).toBeGreaterThanOrEqual(1)
    const roles = screen.getAllByText("Engineering Lead")
    expect(roles.length).toBeGreaterThanOrEqual(1)
  })

  it("renders social share section", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("Share this article")).toBeInTheDocument()
  })

  it("renders related articles section", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("Related Articles")).toBeInTheDocument()
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
    expect(screen.getByText("Article Not Found")).toBeInTheDocument()
    expect(
      screen.getByText("This article does not exist.")
    ).toBeInTheDocument()
    expect(screen.getByText("Back to Blog")).toBeInTheDocument()
  })
})
