import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { type ReactNode } from "react"
import {
  useCreateBlogPost,
  useUpdateBlogPost,
  useDeleteBlogPost,
} from "@/services/queries"
import { adminBlogApi } from "@/api/endpoints"

vi.mock("@/api/endpoints", () => ({
  adminBlogApi: {
    createPost: vi.fn(),
    updatePost: vi.fn(),
    deletePost: vi.fn(),
  },
  authApi: { getMe: vi.fn(), updateProfile: vi.fn(), changePassword: vi.fn() },
  subscriptionApi: { getCurrent: vi.fn(), getPlans: vi.fn() },
  companyApi: { get: vi.fn(), update: vi.fn() },
  supportApi: { createTicket: vi.fn(), getTickets: vi.fn() },
  blogApi: { getPosts: vi.fn(), getPost: vi.fn(), getCategories: vi.fn() },
  changelogApi: { getEntries: vi.fn() },
  roadmapApi: { getItems: vi.fn() },
  statusApi: { getStatus: vi.fn() },
  tutorialsApi: { getTutorials: vi.fn(), getTutorial: vi.fn() },
  developersApi: { getResources: vi.fn(), getToolkitVersions: vi.fn() },
  securityApi: { getReports: vi.fn(), submitReport: vi.fn() },
  announcementsApi: { getAnnouncements: vi.fn() },
  invoicesApi: { getInvoices: vi.fn() },
}))

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }

  return { wrapper: Wrapper, queryClient }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe("useCreateBlogPost", () => {
  it("calls adminBlogApi.createPost with correct data", async () => {
    vi.mocked(adminBlogApi.createPost).mockResolvedValueOnce({
      data: { id: "1" },
    } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateBlogPost(), { wrapper })

    const postData = {
      title: "New Blog Post",
      content: "Post content here",
      excerpt: "Short excerpt",
      category_id: "tech",
      published: true,
    }

    await act(async () => {
      await result.current.mutateAsync(postData)
    })

    expect(adminBlogApi.createPost).toHaveBeenCalledWith(postData)
  })

  it("invalidates blog-posts query on success", async () => {
    vi.mocked(adminBlogApi.createPost).mockResolvedValueOnce({
      data: { id: "1" },
    } as any)

    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(() => useCreateBlogPost(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        title: "Test",
        content: "Content",
        excerpt: "Excerpt",
        category_id: "cat-1",
        published: true,
      })
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["blog-posts"] })
  })
})

describe("useUpdateBlogPost", () => {
  it("calls adminBlogApi.updatePost with slug and data", async () => {
    vi.mocked(adminBlogApi.updatePost).mockResolvedValueOnce({
      data: { id: "1" },
    } as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useUpdateBlogPost(), { wrapper })

    const slug = "my-post-slug"
    const updateData = {
      slug,
      data: {
        title: "Updated Title",
        content: "Updated content",
      },
    }

    await act(async () => {
      await result.current.mutateAsync(updateData)
    })

    expect(adminBlogApi.updatePost).toHaveBeenCalledWith(slug, {
      title: "Updated Title",
      content: "Updated content",
    })
  })
})

describe("useDeleteBlogPost", () => {
  it("calls adminBlogApi.deletePost with slug", async () => {
    vi.mocked(adminBlogApi.deletePost).mockResolvedValueOnce({} as any)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDeleteBlogPost(), { wrapper })

    const slug = "post-to-delete"

    await act(async () => {
      await result.current.mutateAsync(slug)
    })

    expect(adminBlogApi.deletePost).toHaveBeenCalledWith(slug)
  })

  it("invalidates blog-posts query on success", async () => {
    vi.mocked(adminBlogApi.deletePost).mockResolvedValueOnce({} as any)

    const { wrapper, queryClient } = createWrapper()
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries")

    const { result } = renderHook(() => useDeleteBlogPost(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync("post-to-delete")
    })

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["blog-posts"] })
  })
})

describe("Error handling", () => {
  it("Error in create propagates the error", async () => {
    const testError = new Error("Validation failed")
    vi.mocked(adminBlogApi.createPost).mockRejectedValueOnce(testError)

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateBlogPost(), { wrapper })

    await act(async () => {
      try {
        await result.current.mutateAsync({
          title: "Test",
          content: "Content",
          excerpt: "Excerpt",
          category_id: "cat-1",
        })
      } catch (e) {
        expect((e as Error).message).toBe("Validation failed")
      }
    })
  })
})
