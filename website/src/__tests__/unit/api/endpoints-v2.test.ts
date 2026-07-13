import { describe, it, expect, vi, beforeEach } from "vitest"
import {
  blogApi,
  changelogApi,
  roadmapApi,
  statusApi,
  tutorialsApi,
  developersApi,
  securityApi,
  announcementsApi,
  invoicesApi,
  adminBlogApi,
  CreateBlogPostRequest,
  UpdateBlogPostRequest,
} from "@/api/endpoints"
import apiClient from "@/api/client"

vi.mock("@/api/client", {
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
})

describe("blogApi (V2)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("has getPosts method", () => {
    expect(blogApi.getPosts).toBeDefined()
    expect(typeof blogApi.getPosts).toBe("function")
  })

  it("getPosts calls GET /api/blog/posts with optional params", () => {
    const params = { page: 2, category: "releases", tag: "v2" }
    blogApi.getPosts(params)
    expect(apiClient.get).toHaveBeenCalledWith("/api/blog/posts", { params })
  })

  it("getPosts works without params", () => {
    blogApi.getPosts()
    expect(apiClient.get).toHaveBeenCalledWith("/api/blog/posts", { params: undefined })
  })

  it("has getPost method", () => {
    expect(blogApi.getPost).toBeDefined()
    expect(typeof blogApi.getPost).toBe("function")
  })

  it("getPost calls GET /api/blog/posts/:slug", () => {
    blogApi.getPost("hello-world")
    expect(apiClient.get).toHaveBeenCalledWith("/api/blog/posts/hello-world")
  })

  it("has getCategories method", () => {
    expect(blogApi.getCategories).toBeDefined()
    expect(typeof blogApi.getCategories).toBe("function")
  })

  it("getCategories calls GET /api/blog/categories", () => {
    blogApi.getCategories()
    expect(apiClient.get).toHaveBeenCalledWith("/api/blog/categories")
  })

  it("has getAuthor method", () => {
    expect(blogApi.getAuthor).toBeDefined()
    expect(typeof blogApi.getAuthor).toBe("function")
  })

  it("getAuthor calls GET /api/blog/authors/:id", () => {
    blogApi.getAuthor("author-1")
    expect(apiClient.get).toHaveBeenCalledWith("/api/blog/authors/author-1")
  })
})

describe("changelogApi (V2)", () => {
  it("has getEntries method", () => {
    expect(changelogApi.getEntries).toBeDefined()
    expect(typeof changelogApi.getEntries).toBe("function")
  })

  it("getEntries calls GET /api/v1/changelog", () => {
    changelogApi.getEntries()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/changelog")
  })
})

describe("roadmapApi (V2)", () => {
  it("has getItems method", () => {
    expect(roadmapApi.getItems).toBeDefined()
    expect(typeof roadmapApi.getItems).toBe("function")
  })

  it("getItems calls GET /api/v1/roadmap", () => {
    roadmapApi.getItems()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/roadmap", { params: { status: undefined } })
  })

  it("getItems accepts optional status filter", () => {
    roadmapApi.getItems("in_progress")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/roadmap", { params: { status: "in_progress" } })
  })
})

describe("statusApi (V2)", () => {
  it("has getStatus method", () => {
    expect(statusApi.getStatus).toBeDefined()
    expect(typeof statusApi.getStatus).toBe("function")
  })

  it("getStatus calls GET /api/v1/status", () => {
    statusApi.getStatus()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/status")
  })
})

describe("tutorialsApi (V2)", () => {
  it("has getTutorials method", () => {
    expect(tutorialsApi.getTutorials).toBeDefined()
    expect(typeof tutorialsApi.getTutorials).toBe("function")
  })

  it("getTutorials calls GET /api/v1/tutorials with optional params", () => {
    tutorialsApi.getTutorials({ category: "beginner", search: "install" })
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/tutorials", {
      params: { category: "beginner", search: "install" },
    })
  })

  it("getTutorials works without params", () => {
    tutorialsApi.getTutorials()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/tutorials", { params: undefined })
  })

  it("has getTutorial method", () => {
    expect(tutorialsApi.getTutorial).toBeDefined()
    expect(typeof tutorialsApi.getTutorial).toBe("function")
  })

  it("getTutorial calls GET /api/v1/tutorials/:slug", () => {
    tutorialsApi.getTutorial("getting-started")
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/tutorials/getting-started")
  })
})

describe("developersApi (V2)", () => {
  it("has getResources method", () => {
    expect(developersApi.getResources).toBeDefined()
    expect(typeof developersApi.getResources).toBe("function")
  })

  it("getResources calls GET /api/v1/developers/resources", () => {
    developersApi.getResources()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/developers/resources")
  })

  it("has getToolkitVersions method", () => {
    expect(developersApi.getToolkitVersions).toBeDefined()
    expect(typeof developersApi.getToolkitVersions).toBe("function")
  })

  it("getToolkitVersions calls GET /api/v1/developers/toolkit/versions", () => {
    developersApi.getToolkitVersions()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/developers/toolkit/versions")
  })
})

describe("securityApi (V2)", () => {
  it("has getReports method", () => {
    expect(securityApi.getReports).toBeDefined()
    expect(typeof securityApi.getReports).toBe("function")
  })

  it("getReports calls GET /api/v1/security/reports", () => {
    securityApi.getReports()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/security/reports")
  })

  it("has submitReport method", () => {
    expect(securityApi.submitReport).toBeDefined()
    expect(typeof securityApi.submitReport).toBe("function")
  })

  it("submitReport calls POST /api/v1/security/reports with data", () => {
    const data = { title: "XSS Vulnerability", description: "Found in login form", severity: "high" }
    securityApi.submitReport(data)
    expect(apiClient.post).toHaveBeenCalledWith("/api/v1/security/reports", data)
  })
})

describe("announcementsApi (V2)", () => {
  it("has getAnnouncements method", () => {
    expect(announcementsApi.getAnnouncements).toBeDefined()
    expect(typeof announcementsApi.getAnnouncements).toBe("function")
  })

  it("getAnnouncements calls GET /api/v1/announcements", () => {
    announcementsApi.getAnnouncements()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/announcements")
  })
})

describe("invoicesApi (V2)", () => {
  it("has getInvoices method", () => {
    expect(invoicesApi.getInvoices).toBeDefined()
    expect(typeof invoicesApi.getInvoices).toBe("function")
  })

  it("getInvoices calls GET /api/v1/subscriptions/invoices", () => {
    invoicesApi.getInvoices()
    expect(apiClient.get).toHaveBeenCalledWith("/api/v1/subscriptions/invoices")
  })
})

describe("adminBlogApi (V2)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("has createPost method", () => {
    expect(adminBlogApi.createPost).toBeDefined()
    expect(typeof adminBlogApi.createPost).toBe("function")
  })

  it("createPost calls POST /api/admin/blog/posts with data", () => {
    const data: CreateBlogPostRequest = {
      title: "New Post",
      excerpt: "Excerpt",
      content: "Full content",
      category_id: "cat-1",
      tags: ["tag1"],
    }
    adminBlogApi.createPost(data)
    expect(apiClient.post).toHaveBeenCalledWith("/api/admin/blog/posts", data)
  })

  it("has updatePost method", () => {
    expect(adminBlogApi.updatePost).toBeDefined()
    expect(typeof adminBlogApi.updatePost).toBe("function")
  })

  it("updatePost calls PATCH /api/admin/blog/posts/:slug with data", () => {
    const data: UpdateBlogPostRequest = { title: "Updated Title", published: true }
    adminBlogApi.updatePost("my-post", data)
    expect(apiClient.patch).toHaveBeenCalledWith("/api/admin/blog/posts/my-post", data)
  })

  it("has deletePost method", () => {
    expect(adminBlogApi.deletePost).toBeDefined()
    expect(typeof adminBlogApi.deletePost).toBe("function")
  })

  it("deletePost calls DELETE /api/admin/blog/posts/:slug", () => {
    adminBlogApi.deletePost("my-post")
    expect(apiClient.delete).toHaveBeenCalledWith("/api/admin/blog/posts/my-post")
  })
})

describe("CreateBlogPostRequest type", () => {
  it("has required fields", () => {
    const request: CreateBlogPostRequest = {
      title: "Test Title",
      excerpt: "Test excerpt",
      content: "Test content body",
      category_id: "cat-1",
    }
    expect(request.title).toBe("Test Title")
    expect(request.excerpt).toBe("Test excerpt")
    expect(request.content).toBe("Test content body")
    expect(request.category_id).toBe("cat-1")
  })

  it("has optional fields", () => {
    const request: CreateBlogPostRequest = {
      title: "Test",
      excerpt: "Excerpt",
      content: "Content",
      category_id: "cat-1",
      slug: "test-title",
      tags: ["a", "b"],
      featured_image: "/img.png",
      seo_title: "SEO Title",
      seo_description: "SEO Desc",
      published: false,
    }
    expect(request.slug).toBe("test-title")
    expect(request.tags).toEqual(["a", "b"])
    expect(request.featured_image).toBe("/img.png")
    expect(request.seo_title).toBe("SEO Title")
    expect(request.seo_description).toBe("SEO Desc")
    expect(request.published).toBe(false)
  })
})

describe("UpdateBlogPostRequest type", () => {
  it("has all optional fields", () => {
    const request: UpdateBlogPostRequest = {
      title: "Updated",
      slug: "updated-slug",
      excerpt: "Updated excerpt",
      content: "Updated content",
      category_id: "cat-2",
      tags: ["updated"],
      featured_image: "/new.png",
      seo_title: "New SEO Title",
      seo_description: "New SEO Desc",
      published: true,
    }
    expect(request.title).toBe("Updated")
    expect(request.slug).toBe("updated-slug")
    expect(request.excerpt).toBe("Updated excerpt")
    expect(request.content).toBe("Updated content")
    expect(request.category_id).toBe("cat-2")
    expect(request.tags).toEqual(["updated"])
    expect(request.featured_image).toBe("/new.png")
    expect(request.seo_title).toBe("New SEO Title")
    expect(request.seo_description).toBe("New SEO Desc")
    expect(request.published).toBe(true)
  })

  it("can be created with only partial fields", () => {
    const request: UpdateBlogPostRequest = {
      title: "Just the title",
    }
    expect(request.title).toBe("Just the title")
    expect(request.slug).toBeUndefined()
    expect(request.published).toBeUndefined()
  })
})
