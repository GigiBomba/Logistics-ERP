import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import { SeoHead } from "@/components/seo/seo-head"

// ---------------------------------------------------------------------------
// SeoHead
// ---------------------------------------------------------------------------
describe("SeoHead", () => {
  const baseProps = { title: "Test Page", description: "A test description." }

  it("renders nothing with default props (no title or description provided)", () => {
    // Both title and description are required, but we test that empty strings
    // do not crash the component and it still renders without error.
    const { container } = render(
      <SeoHead title="" description="" />
    )
    // Helmet does not render visible DOM children — just verify no crash
    expect(container).toBeTruthy()
  })

  it("sets document title when provided", () => {
    render(<SeoHead {...baseProps} />)
    expect(document.title).toBe("Test Page — Operion")
  })

  it("appends '— Operion' suffix only when title does not already contain 'Operion'", () => {
    render(<SeoHead title="Operion Features" description="Desc" />)
    expect(document.title).toBe("Operion Features")
  })

  it("sets meta description tag when provided", () => {
    render(<SeoHead {...baseProps} />)
    const meta = document.querySelector('meta[name="description"]')
    expect(meta).toBeInTheDocument()
    expect(meta).toHaveAttribute("content", "A test description.")
  })

  describe("OG meta tags", () => {
    it("sets og:title", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[property="og:title"]')
      expect(meta).toHaveAttribute("content", "Test Page — Operion")
    })

    it("sets og:description", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[property="og:description"]')
      expect(meta).toHaveAttribute("content", "A test description.")
    })

    it("sets og:image with default when not provided", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[property="og:image"]')
      expect(meta).toHaveAttribute("content", "https://operion.com/og-image.png")
    })

    it("sets og:image with custom ogImage prop", () => {
      render(<SeoHead {...baseProps} ogImage="https://example.com/custom.png" />)
      const meta = document.querySelector('meta[property="og:image"]')
      expect(meta).toHaveAttribute("content", "https://example.com/custom.png")
    })

    it("sets og:url", () => {
      render(<SeoHead {...baseProps} canonical="https://operion.com/test" />)
      const meta = document.querySelector('meta[property="og:url"]')
      expect(meta).toHaveAttribute("content", "https://operion.com/test")
    })

    it("sets og:type with default value", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[property="og:type"]')
      expect(meta).toHaveAttribute("content", "website")
    })

    it("sets og:type with custom ogType prop", () => {
      render(<SeoHead {...baseProps} ogType="article" />)
      const meta = document.querySelector('meta[property="og:type"]')
      expect(meta).toHaveAttribute("content", "article")
    })

    it("sets og:site_name", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[property="og:site_name"]')
      expect(meta).toHaveAttribute("content", "Operion")
    })

    it("sets og:locale", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[property="og:locale"]')
      expect(meta).toHaveAttribute("content", "en_US")
    })
  })

  describe("Twitter meta tags", () => {
    it("sets twitter:card to summary_large_image", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:card"]')
      expect(meta).toHaveAttribute("content", "summary_large_image")
    })

    it("sets twitter:site", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:site"]')
      expect(meta).toHaveAttribute("content", "@operion")
    })

    it("sets twitter:title", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:title"]')
      expect(meta).toHaveAttribute("content", "Test Page — Operion")
    })

    it("sets twitter:description", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:description"]')
      expect(meta).toHaveAttribute("content", "A test description.")
    })

    it("sets twitter:image", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[name="twitter:image"]')
      expect(meta).toHaveAttribute("content", "https://operion.com/og-image.png")
    })
  })

  describe("canonical link", () => {
    it("sets canonical link tag when provided", () => {
      render(<SeoHead {...baseProps} canonical="https://operion.com/test-page" />)
      const link = document.querySelector('link[rel="canonical"]')
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute("href", "https://operion.com/test-page")
    })

    it("falls back to window.location.href when canonical is not provided", () => {
      render(<SeoHead {...baseProps} />)
      const link = document.querySelector('link[rel="canonical"]')
      expect(link).toBeInTheDocument()
      // In jsdom the default location is http://localhost:3000/
      expect(link).toHaveAttribute("href", "http://localhost:3000/")
    })
  })

  describe("noindex", () => {
    it("does not render noindex meta by default", () => {
      render(<SeoHead {...baseProps} />)
      const meta = document.querySelector('meta[name="robots"]')
      expect(meta).not.toBeInTheDocument()
    })

    it("renders noindex meta when noindex is true", () => {
      render(<SeoHead {...baseProps} noindex />)
      const meta = document.querySelector('meta[name="robots"]')
      expect(meta).toBeInTheDocument()
      expect(meta).toHaveAttribute("content", "noindex, nofollow")
    })
  })

  it("all tags removed when component unmounts (cleanup)", () => {
    const { unmount } = render(<SeoHead {...baseProps} />)

    // Verify tags are present
    expect(document.title).toBe("Test Page — Operion")
    expect(document.querySelector('meta[name="description"]')).toBeInTheDocument()

    unmount()

    // After unmount, Helmet should have cleared the tags
    expect(document.title).toBe("")
    expect(document.querySelector('meta[name="description"]')).not.toBeInTheDocument()
  })

  it("multiple renders update tags correctly", () => {
    const { rerender } = render(
      <SeoHead title="First" description="First description" />
    )
    expect(document.title).toBe("First — Operion")
    expect(
      document.querySelector('meta[name="description"]')
    ).toHaveAttribute("content", "First description")

    rerender(
      <SeoHead title="Second" description="Second description" />
    )
    expect(document.title).toBe("Second — Operion")
    expect(
      document.querySelector('meta[name="description"]')
    ).toHaveAttribute("content", "Second description")
    expect(
      document.querySelector('meta[property="og:title"]')
    ).toHaveAttribute("content", "Second — Operion")
  })

  describe("handles missing optional props gracefully", () => {
    it("renders without crash when only required props are provided", () => {
      expect(() =>
        render(<SeoHead title="Minimal" description="Just required fields" />)
      ).not.toThrow()
    })

    it("uses default ogImage when not provided", () => {
      render(<SeoHead title="No OG Image" description="Desc" />)
      const ogImage = document.querySelector('meta[property="og:image"]')
      expect(ogImage).toHaveAttribute("content", "https://operion.com/og-image.png")
    })

    it("uses default ogType when not provided", () => {
      render(<SeoHead title="No OG Type" description="Desc" />)
      const ogType = document.querySelector('meta[property="og:type"]')
      expect(ogType).toHaveAttribute("content", "website")
    })

    it("handles undefined canonical gracefully (falls back to window.location)", () => {
      render(<SeoHead title="No Canonical" description="Desc" />)
      const link = document.querySelector('link[rel="canonical"]')
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute("href", "http://localhost:3000/")
    })
  })
})
