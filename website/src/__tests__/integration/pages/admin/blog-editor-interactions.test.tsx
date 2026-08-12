import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@/test-utils"
import { Routes, Route } from "react-router"
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

vi.mock("@/hooks/useAppNavigate", () => ({
  useAppNavigate: () => navigateMock,
}))

vi.mock("@/i18n/locale-context", () => {
  const translations: Record<string, string> = {
    "blogEditor.editTitle": "Edit Article - Operion ERP",
    "blogEditor.newTitle": "New Article - Operion ERP",
    "blogEditor.editArticle": "Edit Article",
    "blogEditor.newArticle": "New Article",
    "blogEditor.createDesc": "Create and publish a new blog article.",
    "blogEditor.backToBlog": "Back to Blog",
    "blogEditor.published": "Published",
    "blogEditor.draft": "Draft",
    "blogEditor.title": "Title",
    "blogEditor.titlePlaceholder": "Article title",
    "blogEditor.slug": "Slug",
    "blogEditor.slugAuto": "Auto-generating from title",
    "blogEditor.slugCustom": "Custom slug",
    "blogEditor.slugPlaceholder": "article-slug",
    "blogEditor.excerpt": "Excerpt",
    "blogEditor.excerptPlaceholder": "Short summary displayed in article cards...",
    "blogEditor.content": "Content",
    "blogEditor.contentHint": "Supports Markdown formatting",
    "blogEditor.edit": "Edit",
    "blogEditor.preview": "Preview",
    "blogEditor.previewEmpty": "Start writing to see a preview",
    "blogEditor.contentPlaceholder": "# Introduction\n\nWrite your article content here using Markdown...",
    "blogEditor.publish": "Publish",
    "blogEditor.publishDesc": "Control article visibility.",
    "blogEditor.publishedDesc": "Article is visible to the public.",
    "blogEditor.draftDesc": "Article is hidden from the public.",
    "blogEditor.saveDraft": "Save Draft",
    "blogEditor.category": "Category",
    "blogEditor.categoryPlaceholder": "Select a category",
    "blogEditor.tags": "Tags",
    "blogEditor.tagsHint": "Comma-separated keywords.",
    "blogEditor.tagsPlaceholder": "fleet, logistics, ai ...",
    "blogEditor.featuredImage": "Featured Image",
    "blogEditor.featuredImagePlaceholder": "https://...",
    "blogEditor.featuredImageAlt": "Featured image",
    "blogEditor.seo": "SEO",
    "blogEditor.seoDesc": "Optimize for search engines.",
    "blogEditor.seoTitle": "SEO Title",
    "blogEditor.seoTitlePlaceholder": "Custom page title...",
    "blogEditor.seoDescription": "SEO Description",
    "blogEditor.seoDescriptionPlaceholder": "Meta description...",
    "blogEditor.dangerZone": "Danger Zone",
    "blogEditor.deleteArticle": "Delete Article",
  }
  return {
    useLocale: () => ({ t: (key: string) => translations[key] ?? key, locale: "en", setLocale: vi.fn() }),
    LocaleProvider: ({ children }: any) => <>{children}</>,
  }
})

let navigateMock: ReturnType<typeof vi.fn>

const mockCategories = [
  { id: "cat-1", name: "Product Updates" },
  { id: "cat-2", name: "Tutorials" },
]

const mockExistingPost = {
  title: "Getting Started with Fleet Management",
  slug: "getting-started-fleet-management",
  excerpt: "Learn how to set up and manage your fleet using Operion's powerful dispatch and route optimization tools.",
  content: "# Introduction\n\nThis is a comprehensive guide to fleet management.",
  category_id: "cat-1",
  tags: ["fleet", "guide"],
  featured_image: "",
  seo_title: "",
  seo_description: "",
  published_at: "2026-06-15T00:00:00Z",
}

const makeMutation = (overrides: Record<string, any> = {}) => ({
  mutate: vi.fn(),
  isPending: false,
  ...overrides,
})

function createAdminAuth() {
  return createMockAuthContext({
    user: { id: "1", name: "Admin", email: "admin@operionerp.xyz", role: "admin", is_admin: true },
    isAuthenticated: true,
    isAdmin: true,
  })
}

function renderWithRoute(
  ui: ReactNode,
  { initialEntries = ["/"], routePath }: { initialEntries?: string[]; routePath?: string } = {}
) {
  if (!routePath) return render(<>{ui}</>, { initialEntries })
  return render(
    <Routes>
      <Route path={routePath} element={ui} />
    </Routes>,
    { initialEntries }
  )
}

async function fillCreateForm() {
  const title = screen.getByLabelText(/title \*/i)
  fireEvent.change(title, { target: { value: "My New Fleet Post" } })
  fireEvent.change(screen.getByLabelText(/excerpt \*/i), {
    target: { value: "A detailed look at fleet management best practices for 2026" },
  })
  fireEvent.change(screen.getByLabelText(/content \*/i), {
    target: { value: "# Intro\n\nBody text here" },
  })
  fireEvent.change(screen.getByRole("combobox", { name: /category/i }), { target: { value: "cat-1" } })
  return title
}

describe("BlogEditorPage — interactions (create mode)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock = vi.fn()
    vi.mocked(useAuth).mockReturnValue(createAdminAuth())
    vi.mocked(useBlogPost).mockReturnValue({ data: null, isLoading: false } as any)
    vi.mocked(useBlogCategories).mockReturnValue({ data: mockCategories, isLoading: false } as any)
    vi.mocked(useCreateBlogPost).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateBlogPost).mockReturnValue(makeMutation() as any)
    vi.mocked(useDeleteBlogPost).mockReturnValue(makeMutation() as any)
  })

  it("auto-generates the slug from the title", async () => {
    render(<BlogEditorPage />)
    const title = screen.getByLabelText(/title \*/i)
    fireEvent.change(title, { target: { value: "My New Fleet Post" } })
    await waitFor(() =>
      expect(screen.getByLabelText(/slug \*/i)).toHaveValue("my-new-fleet-post")
    )
  })

  it("allows a custom slug when auto-slug is disabled", async () => {
    render(<BlogEditorPage />)
    fireEvent.click(screen.getByRole("button", { name: /auto-generating from title/i }))
    const slugInput = screen.getByLabelText(/slug \*/i)
    fireEvent.change(slugInput, { target: { value: "custom-handwritten-slug" } })
    expect(slugInput).toHaveValue("custom-handwritten-slug")
  })

  it("saves a draft with published=false and parses tags", async () => {
    const mutate = vi.fn((_payload, opts: any) => opts?.onSuccess?.({ data: { slug: "my-new-fleet-post" } }))
    vi.mocked(useCreateBlogPost).mockReturnValue(makeMutation({ mutate }) as any)
    render(<BlogEditorPage />)

    fireEvent.change(screen.getByLabelText(/title \*/i), { target: { value: "My New Fleet Post" } })
    fireEvent.change(screen.getByLabelText(/excerpt \*/i), {
      target: { value: "A detailed look at fleet management best practices for 2026" },
    })
    fireEvent.change(screen.getByLabelText(/content \*/i), { target: { value: "Body content" } })
    fireEvent.change(screen.getByRole("combobox", { name: /category/i }), { target: { value: "cat-1" } })
    fireEvent.change(screen.getByPlaceholderText(/fleet, logistics/i), {
      target: { value: "fleet, logistics, ai" },
    })

    fireEvent.click(screen.getByRole("button", { name: /save draft/i }))

    await waitFor(() =>
      expect(mutate).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "My New Fleet Post",
          slug: "my-new-fleet-post",
          category_id: "cat-1",
          tags: ["fleet", "logistics", "ai"],
          published: false,
        }),
        expect.anything()
      )
    )
    expect(navigateMock).toHaveBeenCalledWith("/blog/my-new-fleet-post")
  })

  it("publishes a post with published=true", async () => {
    const mutate = vi.fn()
    vi.mocked(useCreateBlogPost).mockReturnValue(makeMutation({ mutate }) as any)
    render(<BlogEditorPage />)
    void fillCreateForm()
    fireEvent.click(screen.getByRole("button", { name: /^publish$/i }))
    await waitFor(() =>
      expect(mutate).toHaveBeenCalledWith(expect.objectContaining({ published: true }), expect.anything())
    )
  })

  it("shows validation errors and does not submit when fields are too short", async () => {
    const mutate = vi.fn()
    vi.mocked(useCreateBlogPost).mockReturnValue(makeMutation({ mutate }) as any)
    render(<BlogEditorPage />)
    fireEvent.change(screen.getByLabelText(/title \*/i), { target: { value: "Ab" } })
    fireEvent.click(screen.getByRole("button", { name: /save draft/i }))
    await waitFor(() =>
      expect(screen.getByText("Title must be at least 5 characters")).toBeInTheDocument()
    )
    expect(mutate).not.toHaveBeenCalled()
  })

  it("renders a category skeleton while categories load", () => {
    vi.mocked(useBlogCategories).mockReturnValue({ data: undefined, isLoading: true } as any)
    render(<BlogEditorPage />)
    expect(screen.getAllByText("Category").length).toBeGreaterThanOrEqual(1)
  })

  it("shows tags as chips as they are typed", () => {
    render(<BlogEditorPage />)
    fireEvent.change(screen.getByPlaceholderText(/fleet, logistics/i), {
      target: { value: "fleet, logistics, ai" },
    })
    expect(screen.getByText("fleet")).toBeInTheDocument()
    expect(screen.getByText("logistics")).toBeInTheDocument()
    expect(screen.getByText("ai")).toBeInTheDocument()
  })

  it("shows a preview of the featured image when a url is entered", () => {
    render(<BlogEditorPage />)
    fireEvent.change(screen.getByPlaceholderText("https://..."), {
      target: { value: "https://example.com/cover.jpg" },
    })
    expect(screen.getByAltText("Featured image")).toHaveAttribute("src", "https://example.com/cover.jpg")
  })})

describe("BlogEditorPage — markdown preview", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock = vi.fn()
    vi.mocked(useAuth).mockReturnValue(createAdminAuth())
    vi.mocked(useBlogPost).mockReturnValue({ data: null, isLoading: false } as any)
    vi.mocked(useBlogCategories).mockReturnValue({ data: mockCategories, isLoading: false } as any)
    vi.mocked(useCreateBlogPost).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateBlogPost).mockReturnValue(makeMutation() as any)
    vi.mocked(useDeleteBlogPost).mockReturnValue(makeMutation() as any)
  })

  const markdown = [
    "# Big Title",
    "## Sub Title",
    "### Small Title",
    "",
    "**bold** and *italic* and ***both*** and `code`",
    "[Operion](https://operionerp.xyz)",
    "<a href=\"javascript:alert(1)\" onclick=\"x()\">evil</a>",
    "",
    "- item one",
    "- item two",
    "1. first",
    "2. second",
    "",
    "plain paragraph",
  ].join("\n")

  it("renders markdown and sanitizes dangerous html", () => {
    render(<BlogEditorPage />)
    fireEvent.change(screen.getByLabelText(/content \*/i), { target: { value: markdown } })
    fireEvent.click(screen.getByRole("tab", { name: /preview/i }))

    const preview = document.querySelector(".prose") as HTMLElement
    expect(preview).toBeTruthy()
    const html = preview.innerHTML

    expect(html).toContain('<h1 class="text-2xl font-bold mt-6 mb-4">Big Title</h1>')
    expect(html).toContain('<h2 class="text-xl font-bold mt-5 mb-3">Sub Title</h2>')
    expect(html).toContain('<h3 class="text-lg font-semibold mt-4 mb-2">Small Title</h3>')
    expect(html).toContain("<strong>bold</strong>")
    expect(html).toContain("<em>italic</em>")
    expect(html).toContain("<em><strong>both</strong></em>")
    expect(html).toContain('<a href="https://operionerp.xyz"')
    // javascript: URLs are neutralised
    expect(html).toContain('<a href="#" class="text-destructive">')
    expect(html).not.toContain("javascript:")
    // inline event handlers are stripped
    expect(html).not.toContain("onclick=")
    // lists
    expect(html).toContain('<ul class="list-disc pl-5 space-y-1 my-3">')
    expect(html).toContain("<li>item one</li>")
    expect(html).toContain('<ol class="list-decimal pl-5 space-y-1 my-3">')
    expect(html).toContain("<li>first</li>")
    // blank line -> <br/> and plain paragraph
    expect(html).toMatch(/<br\s*\/?>/)
    expect(html).toContain('<p class="leading-relaxed my-2">plain paragraph</p>')
  })

  it("shows the empty preview state when there is no content", () => {
    render(<BlogEditorPage />)
    fireEvent.click(screen.getByRole("tab", { name: /preview/i }))
    expect(screen.getByText("Start writing to see a preview")).toBeInTheDocument()
  })
})

describe("BlogEditorPage — interactions (edit mode)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock = vi.fn()
    vi.mocked(useAuth).mockReturnValue(createAdminAuth())
    vi.mocked(useBlogPost).mockReturnValue({ data: mockExistingPost, isLoading: false } as any)
    vi.mocked(useBlogCategories).mockReturnValue({ data: mockCategories, isLoading: false } as any)
    vi.mocked(useCreateBlogPost).mockReturnValue(makeMutation() as any)
    vi.mocked(useUpdateBlogPost).mockReturnValue(makeMutation() as any)
    vi.mocked(useDeleteBlogPost).mockReturnValue(makeMutation() as any)
  })

  it("updates the existing post on submit", async () => {
    const mutate = vi.fn((_args, opts: any) => opts?.onSuccess?.({ data: { slug: "getting-started-fleet-management" } }))
    vi.mocked(useUpdateBlogPost).mockReturnValue(makeMutation({ mutate }) as any)
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })

    fireEvent.change(screen.getByLabelText(/title \*/i), {
      target: { value: "Updated Fleet Management Guide" },
    })
    fireEvent.click(screen.getByRole("button", { name: /save draft/i }))

    await waitFor(() =>
      expect(mutate).toHaveBeenCalledWith(
        {
          slug: "getting-started-fleet-management",
          data: expect.objectContaining({
            title: "Updated Fleet Management Guide",
            published: false,
            tags: ["fleet", "guide"],
          }),
        },
        expect.anything()
      )
    )
    expect(navigateMock).toHaveBeenCalledWith("/blog/getting-started-fleet-management")
  })

  it("deletes the post after confirmation", () => {
    const mutate = vi.fn((_slug, opts: any) => opts?.onSuccess?.())
    vi.mocked(useDeleteBlogPost).mockReturnValue(makeMutation({ mutate }) as any)
    vi.spyOn(window, "confirm").mockReturnValue(true)
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })

    fireEvent.click(screen.getByRole("button", { name: /delete article/i }))
    expect(mutate).toHaveBeenCalledWith("getting-started-fleet-management", expect.anything())
    expect(navigateMock).toHaveBeenCalledWith("/blog")
  })

  it("does not delete when the user cancels the confirm dialog", () => {
    const mutate = vi.fn()
    vi.mocked(useDeleteBlogPost).mockReturnValue(makeMutation({ mutate }) as any)
    vi.spyOn(window, "confirm").mockReturnValue(false)
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })

    fireEvent.click(screen.getByRole("button", { name: /delete article/i }))
    expect(mutate).not.toHaveBeenCalled()
  })

  it("shows the post loading skeleton while fetching the existing post", () => {
    vi.mocked(useBlogPost).mockReturnValue({ data: undefined, isLoading: true } as any)
    renderWithRoute(<BlogEditorPage />, {
      initialEntries: ["/admin/blog/getting-started-fleet-management"],
      routePath: "/admin/blog/:slug",
    })
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0)
  })
})
