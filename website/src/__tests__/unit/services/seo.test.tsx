import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import { getPageTitle, generateMetaTags, StructuredData } from "@/services/seo"
import { seoConfig, siteConfig, socialLinks } from "@/config/site"

// ---------------------------------------------------------------------------
// getPageTitle
// ---------------------------------------------------------------------------
describe("getPageTitle", () => {
  it("returns correct format 'Page — SiteName'", () => {
    expect(getPageTitle("Features")).toBe("Features — Operion")
    expect(getPageTitle("Pricing")).toBe("Pricing — Operion")
  })

  it("handles empty page name", () => {
    expect(getPageTitle("")).toBe(" — Operion")
  })
})

// ---------------------------------------------------------------------------
// generateMetaTags
// ---------------------------------------------------------------------------
describe("generateMetaTags", () => {
  it("returns default tags when no options provided", () => {
    const tags = generateMetaTags()
    expect(tags).toHaveLength(13)

    const desc = tags.find((t) => t.name === "description")
    expect(desc?.content).toBe(seoConfig.defaultDescription)

    const ogTitle = tags.find((t) => t.property === "og:title")
    expect(ogTitle?.content).toBe(seoConfig.defaultTitle)

    const ogImage = tags.find((t) => t.property === "og:image")
    expect(ogImage?.content).toBe(`${siteConfig.url}${siteConfig.ogImage}`)

    const ogUrl = tags.find((t) => t.property === "og:url")
    expect(ogUrl?.content).toBe(siteConfig.url)
  })

  it("includes description, OG tags, and Twitter tags", () => {
    const tags = generateMetaTags({ title: "Test", description: "Desc" })

    const ogProps = tags.map((t) => t.property).filter(Boolean)
    expect(ogProps).toContain("og:title")
    expect(ogProps).toContain("og:description")
    expect(ogProps).toContain("og:image")
    expect(ogProps).toContain("og:url")
    expect(ogProps).toContain("og:type")
    expect(ogProps).toContain("og:site_name")
    expect(ogProps).toContain("og:locale")

    const names = tags.map((t) => t.name).filter(Boolean)
    expect(names).toContain("description")
    expect(names).toContain("twitter:card")
    expect(names).toContain("twitter:site")
    expect(names).toContain("twitter:title")
    expect(names).toContain("twitter:description")
    expect(names).toContain("twitter:image")
  })

  it("uses provided custom options", () => {
    const tags = generateMetaTags({
      title: "Pricing",
      description: "See our plans",
      image: "/pricing.png",
      url: "https://operion.com/pricing",
    })

    expect(tags.find((t) => t.property === "og:title")?.content).toBe(
      "Pricing — Operion"
    )
    expect(tags.find((t) => t.property === "og:description")?.content).toBe(
      "See our plans"
    )
    expect(tags.find((t) => t.property === "og:image")?.content).toBe(
      "https://operion.com/pricing.png"
    )
    expect(tags.find((t) => t.property === "og:url")?.content).toBe(
      "https://operion.com/pricing"
    )
  })

  it("resolves relative image to absolute URL", () => {
    const tags = generateMetaTags({ image: "/custom.png" })
    expect(tags.find((t) => t.property === "og:image")?.content).toBe(
      "https://operion.com/custom.png"
    )
  })

  it("keeps absolute image URL unchanged", () => {
    const tags = generateMetaTags({
      image: "https://cdn.example.com/image.jpg",
    })
    expect(tags.find((t) => t.property === "og:image")?.content).toBe(
      "https://cdn.example.com/image.jpg"
    )
  })
})

// ---------------------------------------------------------------------------
// StructuredData
// ---------------------------------------------------------------------------
describe("StructuredData", () => {
  function getLdJsonScript() {
    return document.querySelector('script[type="application/ld+json"]')
  }

  function parseLdJson() {
    const script = getLdJsonScript()
    expect(script).toBeInTheDocument()
    return JSON.parse(script!.textContent || "")
  }

  it("renders Organization schema with correct type and valid JSON", () => {
    render(<StructuredData type="Organization" />)

    const script = getLdJsonScript()
    expect(script).toBeInTheDocument()
    expect(script).toHaveAttribute("type", "application/ld+json")

    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("Organization")
    expect(parsed["@context"]).toBe("https://schema.org")
    expect(parsed.name).toBe(siteConfig.name)
    expect(parsed.url).toBe(siteConfig.url)
    expect(parsed.logo).toBe(`${siteConfig.url}${siteConfig.ogImage}`)
    expect(parsed.description).toBe(siteConfig.description)
    expect(parsed.sameAs).toEqual([
      socialLinks.twitter,
      socialLinks.github,
      socialLinks.linkedin,
    ])
  })

  it("renders WebSite schema", () => {
    render(<StructuredData type="WebSite" />)

    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("WebSite")
    expect(parsed["@context"]).toBe("https://schema.org")
    expect(parsed.name).toBe(siteConfig.name)
    expect(parsed.url).toBe(siteConfig.url)
    expect(parsed.description).toBe(siteConfig.description)
  })

  it("renders BreadcrumbList schema with provided items", () => {
    const items = [
      { "@type": "ListItem", position: 1, name: "Home", item: "https://operion.com" },
      { "@type": "ListItem", position: 2, name: "Blog", item: "https://operion.com/blog" },
    ]
    render(<StructuredData type="BreadcrumbList" data={{ items }} />)

    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("BreadcrumbList")
    expect(parsed["@context"]).toBe("https://schema.org")
    expect(parsed.itemListElement).toEqual(items)
  })

  it("renders BreadcrumbList with empty array when items are missing", () => {
    render(<StructuredData type="BreadcrumbList" data={{}} />)

    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("BreadcrumbList")
    expect(parsed.itemListElement).toEqual([])
  })

  it("renders BreadcrumbList with empty array when data is undefined", () => {
    render(<StructuredData type="BreadcrumbList" />)

    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("BreadcrumbList")
    expect(parsed.itemListElement).toEqual([])
  })

  it("renders Article schema with custom data", () => {
    const articleData = {
      headline: "Test Article",
      author: "John Doe",
      datePublished: "2026-07-19",
    }
    render(<StructuredData type="Article" data={articleData} />)

    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("Article")
    expect(parsed["@context"]).toBe("https://schema.org")
    expect(parsed.headline).toBe("Test Article")
    expect(parsed.author).toBe("John Doe")
    expect(parsed.datePublished).toBe("2026-07-19")
  })

  it("renders Article schema without data", () => {
    render(<StructuredData type="Article" />)

    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("Article")
    expect(parsed["@context"]).toBe("https://schema.org")
    // Only @context and @type should be present when no data passed
    expect(Object.keys(parsed)).toHaveLength(2)
  })

  it("produces valid parseable JSON for Organization schema", () => {
    render(<StructuredData type="Organization" />)
    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("Organization")
  })

  it("produces valid parseable JSON for WebSite schema", () => {
    render(<StructuredData type="WebSite" />)
    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("WebSite")
  })

  it("produces valid parseable JSON for BreadcrumbList schema", () => {
    render(<StructuredData type="BreadcrumbList" />)
    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("BreadcrumbList")
  })

  it("produces valid parseable JSON for Article schema", () => {
    render(<StructuredData type="Article" />)
    const parsed = parseLdJson()
    expect(parsed["@type"]).toBe("Article")
  })
})
