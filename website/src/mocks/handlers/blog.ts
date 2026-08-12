import { http, HttpResponse } from "msw"
import type { BlogPost, BlogCategory } from "@/types"

const mockCategories: BlogCategory[] = [
  { id: 1, name: "Product Updates", slug: "product-updates", description: "Latest feature releases and improvements", post_count: 3 },
  { id: 2, name: "Tutorials", slug: "tutorials", description: "Step-by-step guides and how-tos", post_count: 2 },
  { id: 3, name: "Industry Insights", slug: "industry-insights", description: "Logistics and supply chain trends", post_count: 1 },
]

const mockPosts: BlogPost[] = [
  {
    id: 1,
    title: "Introducing AI-Powered OCR for Package Recognition",
    slug: "ai-powered-ocr-package-recognition",
    excerpt: "Our new AI-powered OCR engine can recognize package labels with 99.8% accuracy, even in challenging lighting conditions.",
    author_name: "Test User",
    author_avatar: undefined,
    category: "Product Updates",
    category_id: 1,
    tags: ["ai", "ocr", "product"],
    featured_image: undefined,
    reading_time_minutes: 5,
    published_at: "2026-07-20T10:00:00Z",
    created_at: "2026-07-18T08:00:00Z",
    updated_at: "2026-07-20T10:00:00Z",
  },
  {
    id: 2,
    title: "How to Set Up Your First Warehouse Scanning Station",
    slug: "setup-first-warehouse-scanning-station",
    excerpt: "A complete walkthrough for configuring scanning hardware and software for your warehouse.",
    author_name: "Test User",
    author_avatar: undefined,
    category: "Tutorials",
    category_id: 2,
    tags: ["warehouse", "setup", "guide"],
    featured_image: undefined,
    reading_time_minutes: 8,
    published_at: "2026-07-15T09:00:00Z",
    created_at: "2026-07-12T14:00:00Z",
    updated_at: "2026-07-15T09:00:00Z",
  },
  {
    id: 3,
    title: "Summer 2026 Release Notes: Barcode Scanner v2.5",
    slug: "summer-2026-release-notes-v2-5",
    excerpt: "Check out what's new in the Summer 2026 release, including batch scanning and offline mode.",
    author_name: "Test User",
    author_avatar: undefined,
    category: "Product Updates",
    category_id: 1,
    tags: ["release", "v2.5", "offline"],
    featured_image: undefined,
    reading_time_minutes: 4,
    published_at: "2026-07-01T12:00:00Z",
    created_at: "2026-06-28T10:00:00Z",
    updated_at: "2026-07-01T12:00:00Z",
  },
  {
    id: 4,
    title: "The Future of Last-Mile Delivery: Trends for 2026",
    slug: "future-last-mile-delivery-trends-2026",
    excerpt: "Explore the key trends shaping last-mile delivery, from autonomous vehicles to real-time tracking.",
    author_name: "Test User",
    author_avatar: undefined,
    category: "Industry Insights",
    category_id: 3,
    tags: ["delivery", "trends", "logistics"],
    featured_image: undefined,
    reading_time_minutes: 6,
    published_at: "2026-06-25T11:00:00Z",
    created_at: "2026-06-22T09:00:00Z",
    updated_at: "2026-06-25T11:00:00Z",
  },
  {
    id: 5,
    title: "Integrating Operion Scanner with Your Existing ERP System",
    slug: "integrating-operion-scanner-erp",
    excerpt: "Learn how to connect Operion Scanner with popular ERP systems like SAP, Oracle, and Microsoft Dynamics.",
    author_name: "Test User",
    author_avatar: undefined,
    category: "Tutorials",
    category_id: 2,
    tags: ["erp", "integration", "api"],
    featured_image: undefined,
    reading_time_minutes: 10,
    published_at: "2026-06-10T08:00:00Z",
    created_at: "2026-06-05T16:00:00Z",
    updated_at: "2026-06-10T08:00:00Z",
  },
]

export const blogHandlers = [
  http.get("*/api/v1/blog/posts", ({ request }) => {
    const url = new URL(request.url)
    const categoryId = url.searchParams.get("category_id")
    const tag = url.searchParams.get("tag")
    let filtered = mockPosts
    if (categoryId) {
      filtered = filtered.filter((p) => String(p.category_id) === categoryId)
    }
    if (tag) {
      filtered = filtered.filter((p) => p.tags.includes(tag))
    }
    return HttpResponse.json({
      items: filtered,
      total: filtered.length,
      page: 1,
      page_size: 20,
    })
  }),

  http.get("*/api/v1/blog/posts/:slug", ({ params }) => {
    const post = mockPosts.find((p) => p.slug === params.slug)
    if (!post) {
      return HttpResponse.json({ detail: "Post not found" }, { status: 404 })
    }
    return HttpResponse.json({ ...post, content: "Full article content would appear here." })
  }),

  http.get("*/api/v1/blog/categories", () => {
    return HttpResponse.json(mockCategories)
  }),
]
