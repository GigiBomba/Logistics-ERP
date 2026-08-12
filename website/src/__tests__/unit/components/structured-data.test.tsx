import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import {
  JsonLd,
  JsonLdMultiple,
  organizationSchema,
  websiteSchema,
  breadcrumbSchema,
  articleSchema,
  itemListSchema,
  productSchema,
} from "@/components/seo/structured-data"

function readJsonLdScripts(): Record<string, unknown>[] {
  const scripts = Array.from(
    document.querySelectorAll('script[type="application/ld+json"]')
  )
  return scripts.map((s) => JSON.parse(s.textContent || "{}"))
}

describe("structured-data schema builders", () => {
  it("organizationSchema has the expected shape", () => {
    const schema = organizationSchema()
    expect(schema["@type"]).toBe("Organization")
    expect(schema.name).toBe("Operion")
    expect(schema.sameAs).toHaveLength(3)
    expect(schema.contactPoint["@type"]).toBe("ContactPoint")
  })

  it("websiteSchema has a SearchAction", () => {
    const schema = websiteSchema()
    expect(schema["@type"]).toBe("WebSite")
    expect(schema.potentialAction["@type"]).toBe("SearchAction")
  })

  it("breadcrumbSchema builds list items with positions", () => {
    const schema = breadcrumbSchema([
      { name: "Home", url: "/" },
      { name: "Pricing", url: "/pricing" },
    ])
    expect(schema["@type"]).toBe("BreadcrumbList")
    expect(schema.itemListElement).toHaveLength(2)
    expect(schema.itemListElement[1].position).toBe(2)
    expect(schema.itemListElement[1].name).toBe("Pricing")
  })

  it("articleSchema defaults dateModified and publisher", () => {
    const schema = articleSchema({
      headline: "Hello",
      datePublished: "2026-01-01",
      authorName: "Ada",
      url: "https://operionerp.xyz/blog/hello",
    } as any)
    expect(schema.dateModified).toBe("2026-01-01")
    expect(schema.author["@type"]).toBe("Person")
    expect(schema.publisher.name).toBe("Operion")
  })

  it("itemListSchema assigns sequential positions", () => {
    const schema = itemListSchema({ items: [{ title: "A", url: "/a" }] })
    expect(schema.itemListElement[0]).toEqual({
      "@type": "ListItem",
      position: 1,
      name: "A",
      url: "/a",
    })
  })

  it("productSchema defaults the offer when no offers are given", () => {
    const schema = productSchema({
      name: "Operion",
      description: "ERP",
      url: "https://operionerp.xyz",
      price: "99",
    }) as any
    expect(schema.category).toBe("BusinessApplication")
    expect(schema.offers["@type"]).toBe("Offer")
    expect(schema.offers.price).toBe("99")
    expect(schema.offers.priceCurrency).toBe("EUR")
  })

  it("productSchema maps offers when provided", () => {
    const schema = productSchema({
      name: "Operion",
      description: "ERP",
      url: "https://operionerp.xyz",
      price: "99",
      category: "Software",
      offers: [{ name: "Starter", price: "49", priceCurrency: "USD", description: "Basic" }],
    }) as any
    expect(schema.category).toBe("Software")
    expect(Array.isArray(schema.offers)).toBe(true)
    expect(schema.offers[0].name).toBe("Starter")
  })

  it("JsonLd renders the data as JSON", () => {
    const { container } = render(<JsonLd data={{ "@type": "Test" }} />)
    const script = container.querySelector('script[type="application/ld+json"]')
    expect(JSON.parse(script?.textContent || "{}")["@type"]).toBe("Test")
  })

  it("JsonLdMultiple renders one script per schema", () => {
    render(
      <JsonLdMultiple
        schemas={[
          { "@type": "Organization" },
          { "@type": "WebSite" },
        ]}
      />
    )
    const scripts = readJsonLdScripts()
    expect(scripts.map((s) => s["@type"])).toEqual(["Organization", "WebSite"])
  })
})
