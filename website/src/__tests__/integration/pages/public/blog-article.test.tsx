import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import BlogArticlePage from "@/pages/public/blog-article"
import { useAuth } from "@/contexts/auth-provider"
import { useParams } from "react-router"
import { createMockAuthContext } from "@/test-utils"

vi.mock("@/services/queries", () => {
  const mockArticle = {
    title: "Getting Started with Operion",
    slug: "getting-started-with-operion",
    excerpt: "A comprehensive guide to getting started with Operion logistics platform.",
    seo_description: "Learn how to get started with Operion",
    content: "<p>Test content</p>",
    author_name: "Sarah Chen",
    category: "Getting Started",
    tags: ["onboarding", "fleet-setup", "dispatch"],
    reading_time_minutes: 8,
    published_at: "2026-01-15T10:00:00Z",
  }
  const relatedPosts = [
    {
      id: 11,
      title: "Setting Up Your Fleet",
      slug: "setting-up-your-fleet",
      excerpt: "Get your vehicles and drivers into Operion.",
      author_name: "Sarah Chen",
      category: "Getting Started",
      tags: ["onboarding", "fleet-setup"],
      reading_time_minutes: 5,
      published_at: "2026-02-01T10:00:00Z",
    },
  ]
  return {
    useBlogPost: vi.fn((slug: string) => {
      if (slug === "non-existent-article") {
        return { isLoading: false, data: undefined }
      }
      return { isLoading: false, data: mockArticle }
    }),
    useBlogPosts: vi.fn(() => ({
      data: { items: relatedPosts, total: 1 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    })),
  }
})

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
    useParams: vi.fn(() => ({ slug: "getting-started-with-operion" })),
  }
})

describe("BlogArticlePage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ isAdmin: false }))
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
    expect(screen.getByText("Back to all articles")).toBeInTheDocument()
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
    expect(screen.getByText("Transport & Logistics")).toBeInTheDocument()
  })

  it("renders conversion CTA section", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("Streamline Your Transport Operations with Operion ERP")).toBeInTheDocument()
  })

  it("renders related articles with overlapping category/tags", () => {
    render(<BlogArticlePage />)
    expect(screen.getByText("Related Articles")).toBeInTheDocument()
    expect(screen.getByText("Setting Up Your Fleet")).toBeInTheDocument()
  })
})

describe("BlogArticlePage related posts empty", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ isAdmin: false }))
    vi.mocked(useParams).mockReturnValue({ slug: "getting-started-with-operion" })
  })

  it("shows an honest empty state when there are no related articles", async () => {
    const queries = await import("@/services/queries")
    ;(queries.useBlogPosts as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    })
    render(<BlogArticlePage />)
    expect(screen.getByText("Related Articles")).toBeInTheDocument()
    expect(screen.getByText("No related articles published yet. Check back soon.")).toBeInTheDocument()
  })
})

describe("BlogArticlePage not found", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(createMockAuthContext({ isAdmin: false }))
    vi.mocked(useParams).mockReturnValue({ slug: "non-existent-article" })
  })

  it("shows article not found for invalid slug", () => {
    render(<BlogArticlePage />)
    expect(screen.getAllByText("Article Not Found").length).toBeGreaterThanOrEqual(1)
    expect(
      screen.getByText("The article you are looking for does not exist or may have been removed.")
    ).toBeInTheDocument()
    expect(screen.getByText("Back to Blog")).toBeInTheDocument()
  })
})
