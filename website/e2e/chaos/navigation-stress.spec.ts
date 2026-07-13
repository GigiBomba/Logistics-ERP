import { test, expect } from "@playwright/test"

test.describe("Chaos — Navigation Stress", () => {
  test("rapid back/forward navigation across 10+ pages doesn't error", async ({ page }) => {
    const routes = [
      "/", "/features", "/pricing", "/download", "/about", "/mission",
      "/faq", "/contact", "/privacy", "/terms", "/docs", "/blog",
    ]

    // Visit all pages to populate history
    for (const route of routes) {
      await page.goto(route, { waitUntil: "commit" })
    }

    // Rapid back/forward traversal
    for (let i = 0; i < 5; i++) {
      // Go back several pages
      for (let j = 0; j < 3; j++) {
        await page.goBack({ waitUntil: "commit" }).catch(() => {})
      }
      // Go forward several pages
      for (let j = 0; j < 3; j++) {
        await page.goForward({ waitUntil: "commit" }).catch(() => {})
      }
    }

    // Navigate to a known page to confirm app is still functional
    await page.goto("/", { waitUntil: "networkidle" })
    await expect(page.getByRole("heading", { name: /enterprise logistics/i })).toBeVisible()
  })

  test("opening many pages in quick succession doesn't lose state", async ({ page }) => {
    await page.goto("/")

    // Visit pages rapidly and verify each one loads
    const routes = [
      { path: "/features", text: /route planning|features/i },
      { path: "/pricing", text: /pricing|plans/i },
      { path: "/download", text: /download/i },
      { path: "/about", text: /about/i },
      { path: "/mission", text: /mission/i },
      { path: "/faq", text: /faq/i },
      { path: "/contact", text: /contact/i },
      { path: "/blog", text: /blog/i },
      { path: "/status", text: /status|operational/i },
      { path: "/security", text: /security/i },
    ]

    for (const { path, text } of routes) {
      await page.goto(path, { waitUntil: "networkidle", timeout: 15000 })
      await expect(page.getByText(text).first()).toBeVisible()
    }
  })

  test("resizing browser rapidly doesn't break layout", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" })

    const viewports = [
      { width: 375, height: 667 },   // iPhone SE
      { width: 414, height: 896 },   // iPhone 11 Pro Max
      { width: 768, height: 1024 },  // iPad
      { width: 1024, height: 768 },  // iPad landscape
      { width: 1440, height: 900 },  // Desktop
      { width: 1920, height: 1080 }, // Full HD
    ]

    // Rapid resize through all viewports
    for (const vp of viewports) {
      await page.setViewportSize(vp)
      await page.waitForTimeout(100)
    }

    // Verify the page still renders correctly at the final size
    await expect(page.getByRole("heading", { name: /enterprise logistics/i })).toBeVisible()

    // Check that navigation menu is still interactive
    const navLinks = page.locator("nav a, header a").first()
    if (await navLinks.isVisible()) {
      await navLinks.click()
      await page.waitForTimeout(500)
    }
  })
})
