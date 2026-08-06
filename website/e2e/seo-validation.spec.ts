import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

test.describe("SEO Validation", () => {
  const PUBLIC_PAGES = [
    { path: "/", name: "home" },
    { path: "/features", name: "features" },
    { path: "/pricing", name: "pricing" },
    { path: "/about", name: "about" },
    { path: "/faq", name: "faq" },
    { path: "/contact", name: "contact" },
    { path: "/blog", name: "blog" },
    { path: "/download", name: "download" },
  ]

  test("home page has meta description", async ({ page }) => {
    await page.goto("/")
    const metaDescription = await page.getAttribute('meta[name="description"]', "content")
    expect(metaDescription).toBeTruthy()
    expect(metaDescription!.length).toBeGreaterThan(10)
  })

  test("home page has og:title and og:description", async ({ page }) => {
    await page.goto("/")
    const ogTitle = await page.getAttribute('meta[property="og:title"]', "content")
    const ogDescription = await page.getAttribute('meta[property="og:description"]', "content")
    expect(ogTitle).toBeTruthy()
    expect(ogDescription).toBeTruthy()
    expect(ogTitle!.length).toBeGreaterThan(5)
    expect(ogDescription!.length).toBeGreaterThan(10)
  })

  test("home page has twitter:card", async ({ page }) => {
    await page.goto("/")
    const twitterCard = await page.getAttribute('meta[name="twitter:card"]', "content")
    expect(twitterCard).toBeTruthy()
    expect(twitterCard).toBe("summary_large_image")
  })

  test("blog article page has structured data (JSON-LD)", async ({ page }) => {
    await page.goto("/blog/getting-started-with-operion")
    const jsonldScripts = page.locator('script[type="application/ld+json"]')
    const count = await jsonldScripts.count()
    expect(count).toBeGreaterThanOrEqual(1)

    // Verify at least one JSON-LD block contains valid JSON
    for (let i = 0; i < count; i++) {
      const textContent = await jsonldScripts.nth(i).textContent()
      if (textContent) {
        const parsed = JSON.parse(textContent)
        expect(parsed).toHaveProperty("@context")
        expect(parsed["@context"]).toBe("https://schema.org")
      }
    }
  })

  test("canonical URL is set", async ({ page }) => {
    await page.goto("/")
    const canonical = await page.getAttribute('link[rel="canonical"]', "href")
    expect(canonical).toBeTruthy()
    expect(canonical).toContain("operionerp.xyz")
  })

  test("404 page has appropriate title", async ({ page }) => {
    await page.goto("/nonexistent-page")
    await expect(page).toHaveTitle(/not found/i)
  })

  test("each public page has an h1 heading", async ({ page }) => {
    // Seed consent + pin navigator.onLine so hydration is deterministic and
    // waitForHydration's "interactive element" signal isn't satisfied early by
    // the consent dialog (which made the home h1 race to 0 under load).
    stabilizeHydration(page)
    for (const { path, name } of PUBLIC_PAGES) {
      await page.goto(path)
      // Pages are client-rendered (the static shell has no <h1> until React
      // hydrates), so wait for hydration before counting headings.
      await waitForHydration(page)
      // Auto-retrying presence check — a bare count() is a single snapshot and
      // can still race a not-yet-rendered heading.
      await expect(page.locator("h1").first()).toBeVisible()
      const h1Count = await page.locator("h1").count()
      expect(h1Count, `${name} page (${path}) should have at least one h1`).toBeGreaterThanOrEqual(1)
    }
  })

  test("images have alt text on blog pages", async ({ page }) => {
    // Blog list page — featured image has alt text
    await page.goto("/blog")
    const blogImages = page.locator("img")
    const blogImageCount = await blogImages.count()
    if (blogImageCount > 0) {
      for (let i = 0; i < blogImageCount; i++) {
        const alt = await blogImages.nth(i).getAttribute("alt")
        expect(alt, `Blog image ${i} should have alt text`).toBeTruthy()
      }
    }

    // Blog article page — article images have alt text
    await page.goto("/blog/getting-started-with-operion")
    const articleImages = page.locator("img")
    const articleImageCount = await articleImages.count()
    if (articleImageCount > 0) {
      for (let i = 0; i < articleImageCount; i++) {
        const alt = await articleImages.nth(i).getAttribute("alt")
        expect(alt, `Article image ${i} should have alt text`).toBeTruthy()
      }
    }
  })
})
