import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import { HelmetProvider } from "react-helmet-async"
import { getPageTitle, generateMetaTags, StructuredData } from "@/services/seo"
import { SEOHelmet, PageSEO, getPageMeta } from "@/services/seo-improvements"

describe("seo.tsx — getPageTitle", () => {
  it("applies the title template", () => {
    expect(getPageTitle("Features")).toBe("Features — Operion")
  })
})

describe("seo.tsx — generateMetaTags", () => {
  it("returns default tags when no options provided", () => {
    const tags = generateMetaTags()
    expect(tags.length).toBeGreaterThan(0)
    expect(tags.find((t) => t.name === "description")?.content).toContain("logistics operations system")
    expect(tags.find((t) => t.property === "og:title")?.content).toBe("Operion — Logistics Operations System")
    expect(tags.find((t) => t.property === "og:site_name")?.content).toBe("Operion")
    expect(tags.find((t) => t.property === "og:locale")?.content).toBe("en_US")
  })

  it("applies title/description/image/url overrides", () => {
    const tags = generateMetaTags({
      title: "Pricing",
      description: "Flexible plans",
      image: "/custom-og.png",
      url: "https://operionerp.xyz/pricing",
    })
    expect(tags.find((t) => t.name === "description")?.content).toBe("Flexible plans")
    expect(tags.find((t) => t.property === "og:title")?.content).toBe("Pricing — Operion")
    expect(tags.find((t) => t.property === "og:url")?.content).toBe("https://operionerp.xyz/pricing")
    // Relative image is absolutized against the site URL
    expect(tags.find((t) => t.property === "og:image")?.content).toBe("https://operionerp.xyz/custom-og.png")
  })

  it("keeps absolute image URLs untouched", () => {
    const tags = generateMetaTags({ image: "https://cdn.example.com/og.png" })
    expect(tags.find((t) => t.property === "og:image")?.content).toBe("https://cdn.example.com/og.png")
  })
})

describe("seo.tsx — StructuredData", () => {
  it("renders Organization JSON-LD schema", () => {
    render(
      <HelmetProvider>
        <StructuredData type="Organization" />
      </HelmetProvider>
    )
    const script = document.querySelector('script[type="application/ld+json"]')
    expect(script).not.toBeNull()
    const parsed = JSON.parse(script!.textContent || "{}")
    expect(parsed["@type"]).toBe("Organization")
    expect(parsed.name).toBe("Operion")
    expect(parsed.url).toBe("https://operionerp.xyz")
    expect(parsed.sameAs).toHaveLength(3)
  })

  it("renders WebSite schema", () => {
    render(
      <HelmetProvider>
        <StructuredData type="WebSite" />
      </HelmetProvider>
    )
    const script = document.querySelector('script[type="application/ld+json"]')
    const parsed = JSON.parse(script!.textContent || "{}")
    expect(parsed["@type"]).toBe("WebSite")
  })

  it("renders BreadcrumbList with provided items", () => {
    const items = [
      { "@type": "ListItem", position: 1, name: "Home", item: "https://operionerp.xyz" },
    ]
    render(
      <HelmetProvider>
        <StructuredData type="BreadcrumbList" data={{ items }} />
      </HelmetProvider>
    )
    const script = document.querySelector('script[type="application/ld+json"]')
    const parsed = JSON.parse(script!.textContent || "{}")
    expect(parsed["@type"]).toBe("BreadcrumbList")
    expect(parsed.itemListElement).toEqual(items)
  })

  it("renders Article schema merging data", () => {
    render(
      <HelmetProvider>
        <StructuredData type="Article" data={{ headline: "Hello", datePublished: "2026-01-01" }} />
      </HelmetProvider>
    )
    const script = document.querySelector('script[type="application/ld+json"]')
    const parsed = JSON.parse(script!.textContent || "{}")
    expect(parsed["@type"]).toBe("Article")
    expect(parsed.headline).toBe("Hello")
  })

  it("renders Article schema without data", () => {
    render(
      <HelmetProvider>
        <StructuredData type="Article" />
      </HelmetProvider>
    )
    const script = document.querySelector('script[type="application/ld+json"]')
    const parsed = JSON.parse(script!.textContent || "{}")
    expect(parsed["@type"]).toBe("Article")
  })
})

describe("seo-improvements.tsx — SEOHelmet", () => {
  it("renders default title and description meta", () => {
    render(
      <HelmetProvider>
        <SEOHelmet />
      </HelmetProvider>
    )
    const title = document.querySelector("title")
    expect(title?.textContent).toContain("Operion")
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute("href")).toBe("https://operionerp.xyz")
  })
})

describe("seo-improvements.tsx — PageSEO", () => {
  it("renders title/description/canonical with defaults", () => {
    render(
      <HelmetProvider>
        <PageSEO title="Features" description="All features" />
      </HelmetProvider>
    )
    expect(document.querySelector("title")?.textContent).toBe("Features — Operion")
    // canonical derived from the title slug
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute("href")).toBe(
      "https://operionerp.xyz/features"
    )
  })

  it("uses canonicalUrl override and absolute og image", () => {
    render(
      <HelmetProvider>
        <PageSEO
          title="Pricing"
          description="Plans"
          canonicalUrl="https://operionerp.xyz/pricing"
          ogImage="https://cdn.example.com/pricing.png"
        />
      </HelmetProvider>
    )
    expect(document.querySelector('link[rel="canonical"]')?.getAttribute("href")).toBe(
      "https://operionerp.xyz/pricing"
    )
  })

  it("uses explicit type and relative ogImage absolutized", () => {
    render(
      <HelmetProvider>
        <PageSEO title="Blog" description="News" type="article" ogImage="/blog-og.png" />
      </HelmetProvider>
    )
    expect(document.querySelector("title")?.textContent).toBe("Blog — Operion")
  })
})

describe("seo-improvements.tsx — getPageMeta", () => {
  it("returns defaults without options", () => {
    const meta = getPageMeta()
    expect(meta.pageTitle).toBe("Operion — Logistics Operations System")
    expect(meta.description).toContain("logistics operations system")
    expect(meta.url).toBe("https://operionerp.xyz")
    expect(meta.image).toBe("https://operionerp.xyz/logo3.png")
  })

  it("applies title/description overrides", () => {
    const meta = getPageMeta({ title: "Contact", description: "Reach us" })
    expect(meta.pageTitle).toBe("Contact — Operion")
    expect(meta.description).toBe("Reach us")
  })

  it("keeps absolute image and override url", () => {
    const meta = getPageMeta({ image: "https://cdn.example.com/x.png", url: "https://operionerp.xyz/x" })
    expect(meta.image).toBe("https://cdn.example.com/x.png")
    expect(meta.url).toBe("https://operionerp.xyz/x")
  })

  it("absolutizes relative image against the site url", () => {
    const meta = getPageMeta({ image: "/custom-og.png" })
    expect(meta.image).toBe("https://operionerp.xyz/custom-og.png")
  })
})
