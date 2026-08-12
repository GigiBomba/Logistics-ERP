import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import { SEOHelmet, PageSEO } from "@/services/seo-improvements"
import { seoConfig, siteConfig } from "@/config/site"

// ---------------------------------------------------------------------------
// SEOHelmet
// ---------------------------------------------------------------------------
describe("SEOHelmet", () => {
  it("renders without crashing", () => {
    expect(() => render(<SEOHelmet />)).not.toThrow()
  })

  it("sets the default document title", () => {
    render(<SEOHelmet />)
    expect(document.title).toBe(seoConfig.defaultTitle)
  })

  it("sets description meta tag", () => {
    render(<SEOHelmet />)
    const meta = document.querySelector('meta[name="description"]')
    expect(meta).toBeInTheDocument()
    expect(meta).toHaveAttribute("content", seoConfig.defaultDescription)
  })

  describe("OG meta tags", () => {
    it("sets og:title", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[property="og:title"]')
      expect(meta).toHaveAttribute("content", seoConfig.defaultTitle)
    })

    it("sets og:description", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[property="og:description"]')
      expect(meta).toHaveAttribute("content", seoConfig.defaultDescription)
    })

    it("sets og:image as absolute URL", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[property="og:image"]')
      expect(meta).toHaveAttribute(
        "content",
        `${siteConfig.url}${siteConfig.ogImage}`
      )
    })

    it("sets og:url", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[property="og:url"]')
      expect(meta).toHaveAttribute("content", siteConfig.url)
    })

    it("sets og:type", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[property="og:type"]')
      expect(meta).toHaveAttribute("content", "website")
    })

    it("sets og:site_name", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[property="og:site_name"]')
      expect(meta).toHaveAttribute("content", seoConfig.siteName)
    })

    it("sets og:locale", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[property="og:locale"]')
      expect(meta).toHaveAttribute("content", seoConfig.locale)
    })
  })

  describe("Twitter meta tags", () => {
    it("sets twitter:card", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[name="twitter:card"]')
      expect(meta).toHaveAttribute("content", "summary_large_image")
    })

    it("sets twitter:site", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[name="twitter:site"]')
      expect(meta).toHaveAttribute("content", seoConfig.twitterHandle)
    })

    it("sets twitter:title", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[name="twitter:title"]')
      expect(meta).toHaveAttribute("content", seoConfig.defaultTitle)
    })

    it("sets twitter:description", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[name="twitter:description"]')
      expect(meta).toHaveAttribute("content", seoConfig.defaultDescription)
    })

    it("sets twitter:image", () => {
      render(<SEOHelmet />)
      const meta = document.querySelector('meta[name="twitter:image"]')
      expect(meta).toHaveAttribute(
        "content",
        `${siteConfig.url}${siteConfig.ogImage}`
      )
    })
  })

  it("sets canonical link tag", () => {
    render(<SEOHelmet />)
    const link = document.querySelector('link[rel="canonical"]')
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", siteConfig.url)
  })
})

// ---------------------------------------------------------------------------
// PageSEO
// ---------------------------------------------------------------------------
describe("PageSEO", () => {
  const baseProps = {
    title: "Features",
    description: "Explore all Operion features.",
  }

  it("renders without crashing", () => {
    expect(() => render(<PageSEO {...baseProps} />)).not.toThrow()
  })

  it("sets page title using the title template", () => {
    render(<PageSEO {...baseProps} />)
    expect(document.title).toBe("Features — Operion")
  })

  it("sets description meta tag", () => {
    render(<PageSEO {...baseProps} />)
    const meta = document.querySelector('meta[name="description"]')
    expect(meta).toHaveAttribute("content", "Explore all Operion features.")
  })

  describe("OG meta tags", () => {
    it("sets og:title with page title", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[property="og:title"]')
      expect(meta).toHaveAttribute("content", "Features — Operion")
    })

    it("sets og:description with page description", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[property="og:description"]')
      expect(meta).toHaveAttribute(
        "content",
        "Explore all Operion features."
      )
    })

    it("sets og:image using default when not provided", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[property="og:image"]')
      expect(meta).toHaveAttribute(
        "content",
        `${siteConfig.url}${siteConfig.ogImage}`
      )
    })

    it("sets og:image using custom ogImage prop", () => {
      render(
        <PageSEO {...baseProps} ogImage="/custom-og.png" />
      )
      const meta = document.querySelector('meta[property="og:image"]')
      expect(meta).toHaveAttribute(
        "content",
        "https://operion.com/custom-og.png"
      )
    })

    it("keeps absolute ogImage URL unchanged", () => {
      render(
        <PageSEO
          {...baseProps}
          ogImage="https://cdn.example.com/og.png"
        />
      )
      const meta = document.querySelector('meta[property="og:image"]')
      expect(meta).toHaveAttribute(
        "content",
        "https://cdn.example.com/og.png"
      )
    })

    it("sets og:url from canonicalUrl prop", () => {
      render(
        <PageSEO
          {...baseProps}
          canonicalUrl="https://operion.com/features"
        />
      )
      const meta = document.querySelector('meta[property="og:url"]')
      expect(meta).toHaveAttribute(
        "content",
        "https://operion.com/features"
      )
    })

    it("generates og:url from title when canonicalUrl not provided", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[property="og:url"]')
      // Derived from lowercase, dash-separated title
      expect(meta).toHaveAttribute(
        "content",
        "https://operion.com/features"
      )
    })

    it("sets og:type to the provided type", () => {
      render(<PageSEO {...baseProps} type="article" />)
      const meta = document.querySelector('meta[property="og:type"]')
      expect(meta).toHaveAttribute("content", "article")
    })

    it("defaults og:type to 'website'", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[property="og:type"]')
      expect(meta).toHaveAttribute("content", "website")
    })

    it("sets og:site_name", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[property="og:site_name"]')
      expect(meta).toHaveAttribute("content", seoConfig.siteName)
    })

    it("sets og:locale", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[property="og:locale"]')
      expect(meta).toHaveAttribute("content", seoConfig.locale)
    })
  })

  describe("Twitter meta tags", () => {
    it("sets twitter:card to summary_large_image", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:card"]')
      expect(meta).toHaveAttribute("content", "summary_large_image")
    })

    it("sets twitter:site from config", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:site"]')
      expect(meta).toHaveAttribute("content", seoConfig.twitterHandle)
    })

    it("sets twitter:title with page title", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:title"]')
      expect(meta).toHaveAttribute("content", "Features — Operion")
    })

    it("sets twitter:description with page description", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:description"]')
      expect(meta).toHaveAttribute(
        "content",
        "Explore all Operion features."
      )
    })

    it("sets twitter:image", () => {
      render(<PageSEO {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:image"]')
      expect(meta).toBeInTheDocument()
    })
  })

  describe("canonical link", () => {
    it("uses provided canonicalUrl", () => {
      render(
        <PageSEO
          {...baseProps}
          canonicalUrl="https://operion.com/features"
        />
      )
      const link = document.querySelector('link[rel="canonical"]')
      expect(link).toHaveAttribute("href", "https://operion.com/features")
    })

    it("generates canonical URL from title when canonicalUrl not provided", () => {
      render(<PageSEO title="Blog Post Title" description="Desc" />)
      const link = document.querySelector('link[rel="canonical"]')
      expect(link).toHaveAttribute(
        "href",
        "https://operion.com/blog-post-title"
      )
    })

    it("handles multi-word title for canonical generation", () => {
      render(
        <PageSEO
          title="Route Planning Guide"
          description="Desc"
        />
      )
      const link = document.querySelector('link[rel="canonical"]')
      expect(link).toHaveAttribute(
        "href",
        "https://operion.com/route-planning-guide"
      )
    })
  })

  // -- edge cases -----------------------------------------------------------
  describe("edge cases", () => {
    it("handles missing ogImage (uses default)", () => {
      render(<PageSEO title="About" description="About us" />)
      const ogImage = document.querySelector('meta[property="og:image"]')
      expect(ogImage).toHaveAttribute(
        "content",
        `${siteConfig.url}${siteConfig.ogImage}`
      )
    })

    it("handles missing canonicalUrl (generates from title)", () => {
      render(
        <PageSEO title="Enterprise" description="Enterprise features" />
      )
      const canonical = document.querySelector('link[rel="canonical"]')
      expect(canonical).toHaveAttribute(
        "href",
        "https://operion.com/enterprise"
      )
    })

    it("renders with blog type", () => {
      render(
        <PageSEO
          title="Blog Article"
          description="A blog post"
          type="article"
        />
      )
      expect(document.title).toBe("Blog Article — Operion")
      expect(
        document.querySelector('meta[property="og:type"]')
      ).toHaveAttribute("content", "article")
    })
  })
})
