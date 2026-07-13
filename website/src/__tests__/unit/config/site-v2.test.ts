import { describe, it, expect } from "vitest"
import {
  docsConfig,
  blogConfig,
  toolkitConfig,
  analyticsConfig,
  seoConfig,
  socialLinks,
} from "@/config/site"

describe("docsConfig", () => {
  it("has a positive readingSpeedWPM", () => {
    expect(docsConfig.readingSpeedWPM).toBeGreaterThan(0)
  })

  it("has a non-empty categories array", () => {
    expect(docsConfig.categories.length).toBeGreaterThan(0)
  })

  it("each category has required fields", () => {
    for (const category of docsConfig.categories) {
      expect(category).toHaveProperty("id")
      expect(typeof category.id).toBe("string")
      expect(category.id.length).toBeGreaterThan(0)

      expect(category).toHaveProperty("title")
      expect(typeof category.title).toBe("string")
      expect(category.title.length).toBeGreaterThan(0)

      expect(category).toHaveProperty("description")
      expect(typeof category.description).toBe("string")
      expect(category.description.length).toBeGreaterThan(0)

      expect(category).toHaveProperty("icon")
      expect(typeof category.icon).toBe("string")
      expect(category.icon.length).toBeGreaterThan(0)

      expect(category).toHaveProperty("slug")
      expect(typeof category.slug).toBe("string")
      expect(category.slug).toMatch(/^\/docs\//)
    }
  })
})

describe("blogConfig", () => {
  it("has a positive postsPerPage", () => {
    expect(blogConfig.postsPerPage).toBeGreaterThan(0)
  })

  it("featuredPostSlug is a string when present", () => {
    expect(typeof blogConfig.featuredPostSlug).toBe("string")
  })
})

describe("toolkitConfig", () => {
  it("latestVersion matches semver", () => {
    expect(toolkitConfig.latestVersion).toMatch(/^\d+\.\d+\.\d+$/)
  })

  it("releaseDate is a valid date", () => {
    expect(toolkitConfig.releaseDate).toBeTruthy()
    expect(() => new Date(toolkitConfig.releaseDate)).not.toThrow()
    expect(isNaN(Date.parse(toolkitConfig.releaseDate))).toBe(false)
  })

  it("downloadUrl ends with .exe", () => {
    expect(toolkitConfig.downloadUrl).toMatch(/\.exe$/)
  })
})

describe("analyticsConfig", () => {
  it("measurementId is a string", () => {
    expect(typeof analyticsConfig.measurementId).toBe("string")
  })
})

describe("seoConfig", () => {
  it("defaultTitle is a non-empty string", () => {
    expect(seoConfig.defaultTitle).toBeTruthy()
    expect(typeof seoConfig.defaultTitle).toBe("string")
  })

  it("titleTemplate contains %s placeholder", () => {
    expect(seoConfig.titleTemplate).toContain("%s")
  })

  it("defaultDescription has reasonable length", () => {
    expect(seoConfig.defaultDescription.length).toBeGreaterThan(10)
    expect(seoConfig.defaultDescription.length).toBeLessThan(500)
  })
})

describe("socialLinks", () => {
  it("twitter is a URL", () => {
    expect(socialLinks.twitter).toMatch(/^https?:\/\//)
  })

  it("github is a URL", () => {
    expect(socialLinks.github).toMatch(/^https?:\/\//)
  })

  it("linkedin is a URL", () => {
    expect(socialLinks.linkedin).toMatch(/^https?:\/\//)
  })
})
