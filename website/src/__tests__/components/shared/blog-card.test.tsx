import { describe, it, expect } from "vitest"
import { render, screen } from "@/test-utils"
import { BlogCard } from "@/components/shared/blog-card"

const basePost = {
  title: "Getting Started with Fleet Management",
  slug: "getting-started-fleet-management",
  excerpt: "Learn the basics of managing your fleet efficiently with our comprehensive guide.",
  author_name: "Sarah Chen",
  author_avatar: undefined,
  category: "Guides",
  tags: ["fleet", "management"],
  featured_image: undefined,
  reading_time_minutes: 8,
  published_at: "2026-06-15T00:00:00Z",
}

describe("BlogCard", () => {
  it("renders title", () => {
    render(<BlogCard post={basePost} />)
    expect(screen.getByText("Getting Started with Fleet Management")).toBeInTheDocument()
  })

  it("renders excerpt", () => {
    render(<BlogCard post={basePost} />)
    expect(
      screen.getByText(/Learn the basics of managing your fleet efficiently/)
    ).toBeInTheDocument()
  })

  it("renders date", () => {
    render(<BlogCard post={basePost} />)
    expect(screen.getByText("June 15, 2026")).toBeInTheDocument()
  })

  it("renders reading time", () => {
    render(<BlogCard post={basePost} />)
    expect(screen.getByText("8 min read")).toBeInTheDocument()
  })

  it("renders category badge", () => {
    render(<BlogCard post={basePost} />)
    expect(screen.getByText("Guides")).toBeInTheDocument()
  })

  it("links to /blog/:slug", () => {
    render(<BlogCard post={basePost} />)
    const link = screen.getByRole("link")
    expect(link).toHaveAttribute("href", "/blog/getting-started-fleet-management")
  })

  it("renders without featured image when not provided", () => {
    const { container } = render(<BlogCard post={basePost} />)
    const imgs = container.querySelectorAll("img")
    expect(imgs.length).toBe(0)
  })

  it("renders featured image when provided", () => {
    const postWithImage = {
      ...basePost,
      featured_image: "/images/fleet-guide.jpg",
    }
    const { container } = render(<BlogCard post={postWithImage} />)
    const img = container.querySelector("img")
    expect(img).toHaveAttribute("src", "/images/fleet-guide.jpg")
    expect(img).toHaveAttribute("alt", "Getting Started with Fleet Management")
  })
})
