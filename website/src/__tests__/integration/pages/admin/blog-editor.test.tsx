import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import BlogEditorPage from "@/pages/admin/blog-editor"
import { useAuth } from "@/contexts/auth-provider"
import { useParams } from "react-router"
import {
  useBlogPost,
  useBlogCategories,
  useCreateBlogPost,
  useUpdateBlogPost,
  useDeleteBlogPost,
} from "@/services/queries"
import { createMockAuthContext } from "@/test-utils"

vi.mock("motion/react", () => ({
  motion: { div: ({ children, ...props }: any) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

vi.mock("@/services/queries", () => ({
  useBlogPost: vi.fn(),
  useBlogCategories: vi.fn(),
  useCreateBlogPost: vi.fn(),
  useUpdateBlogPost: vi.fn(),
  useDeleteBlogPost: vi.fn(),
}))

vi.mock("@/contexts/auth-provider", () => ({
  useAuth: vi.fn(),
}))

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router")
  return { ...(actual as object), useParams: vi.fn(() => ({})) }
})

function renderWithRoute(_initialRoute = "/admin/blog/editor") {
  return render(<BlogEditorPage />)
}

const mockAdmin = createMockAuthContext({ isAdmin: true })

const mockCategories = [
  { id: "cat-1", name: "Product Updates", slug: "product-updates", post_count: 5 },
  { id: "cat-2", name: "Engineering", slug: "engineering", post_count: 3 },
  { id: "cat-3", name: "Logistics", slug: "logistics", post_count: 4 },
]

describe("BlogEditorPage — Create Mode", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(mockAdmin)
    vi.mocked(useBlogPost).mockReturnValue({ isLoading: false })
    vi.mocked(useBlogCategories).mockReturnValue({ isLoading: false, data: mockCategories })
    vi.mocked(useCreateBlogPost).mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    vi.mocked(useUpdateBlogPost).mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    vi.mocked(useDeleteBlogPost).mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it("renders create form", () => {
    renderWithRoute()
    const headings = screen.getAllByText("New Article")
    expect(headings.length).toBeGreaterThanOrEqual(1)
  })
})

describe("BlogEditorPage — Edit Mode", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(mockAdmin)
    vi.mocked(useParams).mockReturnValue({ slug: "test-post" })
    vi.mocked(useBlogPost).mockReturnValue({
      isLoading: false,
      data: {
        id: "1",
        title: "Test Post",
        slug: "test-post",
        excerpt: "This is a test blog post excerpt with enough text.",
        content: "Full content of the test blog post.",
        category_id: "cat-1",
        tags: ["tag1", "tag2"],
        featured_image: "",
        seo_title: "SEO Title",
        seo_description: "SEO Desc",
        published: true,
      },
    })
    vi.mocked(useBlogCategories).mockReturnValue({ isLoading: false, data: mockCategories })
    vi.mocked(useCreateBlogPost).mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    vi.mocked(useUpdateBlogPost).mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    vi.mocked(useDeleteBlogPost).mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  })

  it("renders edit form", () => {
    renderWithRoute()
    const headings = screen.getAllByText("Edit Article")
    expect(headings.length).toBeGreaterThanOrEqual(1)
  })
})
