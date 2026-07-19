import { describe, it, expect } from "vitest"
import { render } from "@/test-utils"
import {
  JsonLd,
  organizationSchema,
  websiteSchema,
  softwareApplicationSchema,
  faqSchema,
  breadcrumbSchema,
  contactPageSchema,
} from "@/components/seo/structured-data"

// ---------------------------------------------------------------------------
// JsonLd component
// ---------------------------------------------------------------------------
describe("JsonLd", () => {
  function getScript(): HTMLScriptElement | null {
    return document.querySelector('script[type="application/ld+json"]')
  }

  function parseScript(): Record<string, unknown> {
    const script = getScript()
    expect(script).toBeInTheDocument()
    expect(script).toHaveAttribute("type", "application/ld+json")
    return JSON.parse(script!.textContent || "")
  }

  it("renders JSON-LD script tag with correct type", () => {
    render(<JsonLd data={{ "@context": "https://schema.org", "@type": "Thing" }} />)
    const script = getScript()
    expect(script).toBeInTheDocument()
    expect(script).toHaveAttribute("type", "application/ld+json")
  })

  it("renders valid JSON that is parseable", () => {
    render(<JsonLd data={{ "@context": "https://schema.org", "@type": "Thing" }} />)
    expect(() => parseScript()).not.toThrow()
  })

  it("renders arbitrary schema data correctly", () => {
    const data = {
      "@context": "https://schema.org",
      "@type": "Product",
      name: "Test Product",
      price: "9.99",
    }
    render(<JsonLd data={data} />)
    const parsed = parseScript()
    expect(parsed["@context"]).toBe("https://schema.org")
    expect(parsed["@type"]).toBe("Product")
    expect(parsed.name).toBe("Test Product")
    expect(parsed.price).toBe("9.99")
  })

  it("multiple JsonLd components on the same page don't conflict", () => {
    render(
      <>
        <JsonLd data={{ "@context": "https://schema.org", "@type": "Organization", name: "Org1" }} />
        <JsonLd data={{ "@context": "https://schema.org", "@type": "WebSite", name: "Site1" }} />
      </>
    )
    const scripts = document.querySelectorAll('script[type="application/ld+json"]')
    expect(scripts).toHaveLength(2)

    const parsed1 = JSON.parse(scripts[0]!.textContent || "")
    const parsed2 = JSON.parse(scripts[1]!.textContent || "")
    expect(parsed1["@type"]).toBe("Organization")
    expect(parsed1.name).toBe("Org1")
    expect(parsed2["@type"]).toBe("WebSite")
    expect(parsed2.name).toBe("Site1")
  })
})

// ---------------------------------------------------------------------------
// Schema helper functions
// ---------------------------------------------------------------------------
describe("organizationSchema", () => {
  it("returns valid Organization schema with correct @type and @context", () => {
    const schema = organizationSchema()
    expect(schema["@type"]).toBe("Organization")
    expect(schema["@context"]).toBe("https://schema.org")
  })

  it("includes required Organization fields", () => {
    const schema = organizationSchema()
    expect(schema.name).toBe("Operion")
    expect(schema.url).toBe("https://operion.com")
    expect(schema.logo).toBe("https://operion.com/favicon.svg")
    expect(schema.description).toContain("logistics management")
    expect(schema.email).toBe("operion.contact@gmail.com")
  })

  it("includes sameAs social links", () => {
    const schema = organizationSchema()
    expect(schema.sameAs).toBeInstanceOf(Array)
    expect(schema.sameAs).toHaveLength(3)
    expect(schema.sameAs).toContain("https://twitter.com/operion")
    expect(schema.sameAs).toContain("https://github.com/operion")
    expect(schema.sameAs).toContain("https://linkedin.com/company/operion")
  })

  it("includes contactPoint with correct shape", () => {
    const schema = organizationSchema()
    expect(schema.contactPoint).toBeDefined()
    expect(schema.contactPoint).toHaveProperty("@type", "ContactPoint")
    expect(schema.contactPoint).toHaveProperty("contactType", "customer service")
  })

  it("produces parseable JSON", () => {
    expect(() => JSON.parse(JSON.stringify(organizationSchema()))).not.toThrow()
  })
})

describe("websiteSchema", () => {
  it("returns valid WebSite schema with correct @type and @context", () => {
    const schema = websiteSchema()
    expect(schema["@type"]).toBe("WebSite")
    expect(schema["@context"]).toBe("https://schema.org")
  })

  it("includes required WebSite fields", () => {
    const schema = websiteSchema()
    expect(schema.name).toBe("Operion")
    expect(schema.url).toBe("https://operion.com")
    expect(schema.description).toContain("logistics management")
  })

  it("includes potentialAction (SearchAction)", () => {
    const schema = websiteSchema()
    expect(schema.potentialAction).toBeDefined()
    expect(schema.potentialAction).toHaveProperty("@type", "SearchAction")
    expect(schema.potentialAction).toHaveProperty(
      "target",
      "https://operion.com/search?q={search_term_string}"
    )
    expect(schema.potentialAction).toHaveProperty(
      "query-input",
      "required name=search_term_string"
    )
  })

  it("produces parseable JSON", () => {
    expect(() => JSON.parse(JSON.stringify(websiteSchema()))).not.toThrow()
  })
})

describe("softwareApplicationSchema", () => {
  it("returns valid SoftwareApplication schema", () => {
    const schema = softwareApplicationSchema()
    expect(schema["@type"]).toBe("SoftwareApplication")
    expect(schema["@context"]).toBe("https://schema.org")
  })

  it("includes application category, OS, and version", () => {
    const schema = softwareApplicationSchema()
    expect(schema.applicationCategory).toBe("BusinessApplication")
    expect(schema.operatingSystem).toBe("Windows 10, Windows 11")
    expect(schema.softwareVersion).toBe("0.1.0")
  })

  it("includes offers with free pricing", () => {
    const schema = softwareApplicationSchema()
    expect(schema.offers).toBeDefined()
    expect(schema.offers).toHaveProperty("@type", "Offer")
    expect(schema.offers).toHaveProperty("price", "0")
    expect(schema.offers).toHaveProperty("priceCurrency", "EUR")
  })

  it("includes feature list", () => {
    const schema = softwareApplicationSchema()
    expect(schema.featureList).toBeInstanceOf(Array)
    expect(schema.featureList).toContain("Trip Profit Calculator")
    expect(schema.featureList).toContain("Dispatch Board")
  })

  it("produces parseable JSON", () => {
    expect(() => JSON.parse(JSON.stringify(softwareApplicationSchema()))).not.toThrow()
  })
})

describe("faqSchema", () => {
  it("returns valid FAQPage schema with items", () => {
    const items = [
      { question: "Q1?", answer: "A1." },
      { question: "Q2?", answer: "A2." },
    ]
    const schema = faqSchema(items)
    expect(schema["@type"]).toBe("FAQPage")
    expect(schema["@context"]).toBe("https://schema.org")

    expect(schema.mainEntity).toHaveLength(2)
    expect(schema.mainEntity[0]).toHaveProperty("@type", "Question")
    expect(schema.mainEntity[0]).toHaveProperty("name", "Q1?")
    expect(schema.mainEntity[0].acceptedAnswer).toHaveProperty("@type", "Answer")
    expect(schema.mainEntity[0].acceptedAnswer).toHaveProperty("text", "A1.")
    expect(schema.mainEntity[1]).toHaveProperty("name", "Q2?")
    expect(schema.mainEntity[1].acceptedAnswer).toHaveProperty("text", "A2.")
  })

  it("handles empty items array gracefully", () => {
    const schema = faqSchema([])
    expect(schema["@type"]).toBe("FAQPage")
    expect(schema.mainEntity).toEqual([])
  })

  it("produces parseable JSON", () => {
    const items = [{ question: "Q", answer: "A" }]
    expect(() => JSON.parse(JSON.stringify(faqSchema(items)))).not.toThrow()
  })
})

describe("breadcrumbSchema", () => {
  it("returns valid BreadcrumbList schema with items", () => {
    const items = [
      { name: "Home", url: "https://operion.com" },
      { name: "Blog", url: "https://operion.com/blog" },
      { name: "Post", url: "https://operion.com/blog/post" },
    ]
    const schema = breadcrumbSchema(items)
    expect(schema["@type"]).toBe("BreadcrumbList")
    expect(schema["@context"]).toBe("https://schema.org")

    expect(schema.itemListElement).toHaveLength(3)
    expect(schema.itemListElement[0]).toEqual({
      "@type": "ListItem",
      position: 1,
      name: "Home",
      item: "https://operion.com",
    })
    expect(schema.itemListElement[1]).toEqual({
      "@type": "ListItem",
      position: 2,
      name: "Blog",
      item: "https://operion.com/blog",
    })
    expect(schema.itemListElement[2]).toEqual({
      "@type": "ListItem",
      position: 3,
      name: "Post",
      item: "https://operion.com/blog/post",
    })
  })

  it("handles empty items array gracefully", () => {
    const schema = breadcrumbSchema([])
    expect(schema["@type"]).toBe("BreadcrumbList")
    expect(schema.itemListElement).toEqual([])
  })

  it("produces parseable JSON", () => {
    const items = [{ name: "Home", url: "https://operion.com" }]
    expect(() => JSON.parse(JSON.stringify(breadcrumbSchema(items)))).not.toThrow()
  })
})

describe("contactPageSchema", () => {
  it("returns valid ContactPage schema", () => {
    const schema = contactPageSchema()
    expect(schema["@type"]).toBe("ContactPage")
    expect(schema["@context"]).toBe("https://schema.org")
  })

  it("includes name and url", () => {
    const schema = contactPageSchema()
    expect(schema.name).toBe("Contact Operion")
    expect(schema.url).toBe("https://operion.com/contact")
  })

  it("includes mainEntity Organization", () => {
    const schema = contactPageSchema()
    expect(schema.mainEntity).toBeDefined()
    expect(schema.mainEntity).toHaveProperty("@type", "Organization")
    expect(schema.mainEntity).toHaveProperty("name", "Operion")
    expect(schema.mainEntity).toHaveProperty("email", "operion.contact@gmail.com")
    expect(schema.mainEntity).toHaveProperty("telephone", "+40-123-456-789")
  })

  it("produces parseable JSON", () => {
    expect(() => JSON.parse(JSON.stringify(contactPageSchema()))).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// Combined: all schema outputs are valid parseable JSON
// ---------------------------------------------------------------------------
describe("all schema outputs are parseable JSON", () => {
  const schemaFactories: Array<() => Record<string, unknown>> = [
    organizationSchema,
    websiteSchema,
    softwareApplicationSchema,
    contactPageSchema,
    () => faqSchema([{ question: "Q", answer: "A" }]),
    () => breadcrumbSchema([{ name: "Home", url: "https://operion.com" }]),
  ]

  it.each(schemaFactories)("produces valid JSON without syntax errors", (factory) => {
    const output = factory()
    expect(() => JSON.parse(JSON.stringify(output))).not.toThrow()
    // Verify it's a proper object with @context and @type
    expect(output["@context"]).toBe("https://schema.org")
    expect(output["@type"]).toBeDefined()
  })
})
