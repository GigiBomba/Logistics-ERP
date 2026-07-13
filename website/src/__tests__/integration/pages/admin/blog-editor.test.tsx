import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@/test-utils"
import { MemoryRouter, Route, Routes } from "react-router"
import BlogEditorPage from "@/pages/admin/blog-editor"
import { useAuth } from "@/contexts/auth-provider"
import {
  useBlogPost,
  useBlogCategories,
  useCreateBlogPost,
  useUpdateBlogPost,
  useDeleteBlogPost,
} from "@/services/queries"
import { createMockAuthContext } from "@/test-utils"
import type { ReactNode } from "react"

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

const mockCategories = [
  { id: "cat-1", name: "Product Updates" },
  { id: "cat-2", name: "Tutorials" },
  { id: "cat-3", name: "Company News" },
]

const mockExistingPost = {
  title: "Getting Started with Fleet Management",
  slug: "getting-started-fleet-management",
  excerpt: "Learn how to set up and manage your fleet using Operion's powerful dispatch and route optimization tools.",
  content: "# Introduction\n\nThis is a comprehensive guide to fleet management.",
  category_id: "cat-1",
  tags: ["fleet", "guide", "getting-started"],
  featured_image: "https://images.unsplash.com/photo-123",
  seo_title: "Fleet Management Guide | Operion",
  seo_description: "Complete guide to managing your fleet with Operion ERP.",
  published_at: "2026-06-15T00:00:00Z",
}

function createAdminAuth() {
  return createMockAuthContext({
    user: { id: "1", name: "Admin", email: "admin@operion.com", role: "admin" },
    isAuthenticated: true,
    isAdmin: true,
  })
}

function createUserAuth() {
  return createMockAuthContext({
    user: { id: "2", name: "User", email: "user@operion.com", role: "dispatcher", is_admin: false },
    isAuthenticated: true,
    isAdmin: false,
  })
}

interface RenderInRouterOptions {
  initialEntries?: string[]
  routePath?: string
}

function renderWithRoute(
  ui: ReactNode,
  { initialEntries = ["/"], routePath }: RenderInRouterOptions = {}
) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={initialEntries}>
      {routePath ? (
        <Routes>
          <Route path={routePath} element={children} />
        </Routes>
      ) : (
        children
      )}
    </MemoryRouter>
  )
  return render(<>{ui}</>, { wrapper: Wrapper })
}

describe("BlogEditorPage — Create Mode", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(createAdminAuth())
    vi.mocked(useBlogPost).mockReturnValue({ data: null, isLoading: false } as any)
    vi.mocked(useBlogCategories).mockReturnValue({ data: mockCategories, isLoading: false } as any)
    vi.mocked(useCreateBlogPost).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
    vi.mocked(useUpdateBlogPost).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
    vi.mocked(useDeleteBlogPost).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
  })

  it('renders "New Article" heading in create mode', () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("New Article")).toBeInTheDocument()
  })

  it("renders title, excerpt, and content fields", () => {
    render(<BlogEditorPage />)
    expect(screen.getByLabelText(/title \*/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/excerpt \*/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/content \*/i)).toBeInTheDocument()
  })

  it("shows category dropdown with options", () => {
    render(<BlogEditorPage />)
    // "Category" appears as both the card title and the form label
    expect(screen.getAllByText("Category").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Product Updates")).toBeInTheDocument()
    expect(screen.getByText("Tutorials")).toBeInTheDocument()
    expect(screen.getByText("Company News")).toBeInTheDocument()
  })

  it("shows tags input with placeholder", () => {
    render(<BlogEditorPage />)
    expect(screen.getByPlaceholderText(/fleet, logistics, ai/i)).toBeInTheDocument()
  })

  it("shows publish / save draft buttons", () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("Save Draft")).toBeInTheDocument()
    // "Publish" appears as both the status text (Draft/Published toggle) and the button text
    expect(screen.getAllByText("Publish").length).toBeGreaterThanOrEqual(1)
  })

  it("shows markdown edit/preview tabs", () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("Edit")).toBeInTheDocument()
    expect(screen.getByText("Preview")).toBeInTheDocument()
  })

  it("shows SEO fields (SEO Title and SEO Description)", () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("SEO")).toBeInTheDocument()
    expect(screen.getByText("SEO Title")).toBeInTheDocument()
    expect(screen.getByText("SEO Description")).toBeInTheDocument()
  })

  it("shows slug field with auto-generate toggle", () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("Slug")).toBeInTheDocument()
    expect(screen.getByText("Auto-generating from title")).toBeInTheDocument()
  })

  it("shows featured image input", () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("Featured Image")).toBeInTheDocument()
  })

  it("shows back to blog link", () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("Back to Blog")).toBeInTheDocument()
  })

  it("does not show danger zone in create mode", () => {
    render(<BlogEditorPage />)
    expect(screen.queryByText("Danger Zone")).not.toBeInTheDocument()
    expect(screen.queryByText("Delete Article")).not.toBeInTheDocument()
  })
})

describe("BlogEditorPage — Edit Mode", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(createAdminAuth())
    vi.mocked(useBlogPost).mockReturnValue({ data: mockExistingPost, isLoading: false } as any)
    vi.mocked(useBlogCategories).mockReturnValue({ data: mockCategories, isLoading: false } as any)
    vi.mocked(useCreateBlogPost).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
    vi.mocked(useUpdateBlogPost).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
    vi.mocked(useDeleteBlogPost).mockReturnValue({ mutate: vi.fn(), isPending: false } as any)
  })

  it('renders "Edit Article" heading in edit mode', () => {
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })
    expect(screen.getByText("Edit Article")).toBeInTheDocument()
  })

  it("pre-fills form fields with existing post data", () => {
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })
    expect(screen.getByDisplayValue("Getting Started with Fleet Management")).toBeInTheDocument()
    expect(screen.getByDisplayValue("getting-started-fleet-management")).toBeInTheDocument()
  })

  it("shows published badge for existing post", () => {
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })
    // "Published" appears as both the badge and the publish toggle status text
    expect(screen.getAllByText("Published").length).toBeGreaterThanOrEqual(1)
  })

  it("shows danger zone with delete button in edit mode", () => {
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })
    expect(screen.getByText("Danger Zone")).toBeInTheDocument()
    expect(screen.getByText("Delete Article")).toBeInTheDocument()
  })

  it("shows custom slug toggle when editing", () => {
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })
    expect(screen.getByText("Custom slug")).toBeInTheDocument()
  })
})

describe("BlogEditorPage — Access Denied", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAuth).mockReturnValue(createUserAuth())
    vi.mocked(useBlogPost).mockReturnValue({ data: null, isLoading: false } as any)
    vi.mocked(useBlogCategories).mockReturnValue({ data: [], isLoading: false } as any)
  })

  it("shows access denied for non-admin users", () => {
    render(<BlogEditorPage />)
    expect(screen.getByText("Access Denied")).toBeInTheDocument()
    expect(screen.getByText(/You do not have permission/i)).toBeInTheDocument()
  })

  it("does not render editor form for non-admin users", () => {
    render(<BlogEditorPage />)
    expect(screen.queryByText("New Article")).not.toBeInTheDocument()
    expect(screen.queryByText("SEO")).not.toBeInTheDocument()
  })
})
