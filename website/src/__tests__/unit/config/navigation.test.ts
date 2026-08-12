import { describe, it, expect } from "vitest"
import { publicNavItems, footerNavSections } from "@/config/navigation"

describe("publicNavItems", () => {
  it("has the correct number of top-level items", () => {
    expect(publicNavItems).toHaveLength(10)
  })

  it("each item has label and href", () => {
    for (const item of publicNavItems) {
      expect(item.label).toBeTruthy()
      expect(item.href).toMatch(/^\//)
    }
  })

  it("starts with Home", () => {
    expect(publicNavItems[0].label).toBe("Home")
    expect(publicNavItems[0].href).toBe("/")
  })

  it("includes all required links (top-level)", () => {
    const labels = publicNavItems.map((i) => i.label)
    expect(labels).toContain("Pricing")
    expect(labels).toContain("Download")
    expect(labels).toContain("About")
    expect(labels).toContain("Contact")
  })

  it("includes Features as a child of Product", () => {
    const product = publicNavItems.find((i) => i.label === "Product")
    expect(product).toBeDefined()
    const childLabels = product!.children?.map((c) => c.label) ?? []
    expect(childLabels).toContain("Features")
  })
})

describe("footerNavSections", () => {
  it("has 5 sections", () => {
    expect(footerNavSections).toHaveLength(5)
  })

  it("each section has a title and items", () => {
    for (const section of footerNavSections) {
      expect(section.title).toBeTruthy()
      expect(section.items.length).toBeGreaterThan(0)
    }
  })

  it("section titles are as expected", () => {
    const titles = footerNavSections.map((s) => s.title)
    expect(titles).toContain("Product")
    expect(titles).toContain("Company")
    expect(titles).toContain("Resources")
    expect(titles).toContain("Legal")
  })

  it("Product section has correct links", () => {
    const product = footerNavSections.find((s) => s.title === "Product")!
    const labels = product.items.map((i) => i.label)
    expect(labels).toContain("Features")
    expect(labels).toContain("Products")
    expect(labels).toContain("Pricing")
    expect(labels).toContain("Integrations Explorer")
    expect(labels).toContain("API Playground")
    expect(labels).toContain("Download")
    expect(labels).toContain("Roadmap")
  })

  it("Legal section has Privacy and Terms", () => {
    const legal = footerNavSections.find((s) => s.title === "Legal")!
    const labels = legal.items.map((i) => i.label)
    expect(labels).toContain("Privacy Policy")
    expect(labels).toContain("Terms of Service")
  })

  it("Resources section has Documentation, FAQ, Support", () => {
    const resources = footerNavSections.find((s) => s.title === "Resources")!
    const labels = resources.items.map((i) => i.label)
    expect(labels).toContain("Documentation")
    expect(labels).toContain("FAQ")
    expect(labels).toContain("Support")
  })
})
