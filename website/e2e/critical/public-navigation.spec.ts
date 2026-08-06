import { test, expect } from "@playwright/test"
import { mockAuthAs, createUser, stabilizeHydration } from "../helpers"

/**
 * Public Navigation Tests
 *
 * Navigates all public pages and verifies:
 *   - No 500 errors (page loads without crash)
 *   - Key content elements are rendered
 *   - No console errors occur during navigation
 *
 * NOTE: assertions match the current page copy (the homepage/features/pricing
 * were redesigned — see git history). Selectors are role/text based.
 */

test.describe("Public Navigation", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  test("home page loads with all key sections", async ({ page }) => {
    const errors: string[] = []
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text())
    })

    // The AuthProvider POSTs /api/v1/auth/refresh on mount. Against a reachable
    // real API that returns 422 (no cookie) the browser logs "Failed to load
    // resource" — which this test counts as a console error. Mock the cookie
    // refresh bootstrap + /me (and all data endpoints) so the page is
    // deterministic and free of expected network errors.
    await page.route("**/api/v1/**", async (route) => {
      const url = route.request().url()
      if (url.includes("/api/v1/auth/refresh") || url.includes("/api/v1/auth/me")) {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
    await mockAuthAs(page, createUser("driver"))

    await page.goto("/")
    await expect(page).toHaveTitle(/Operion/)
    await expect(page.getByRole("heading", { name: /The Complete Logistics Operating System/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /waitlist|early access/i }).first()).toBeVisible()
    await expect(page.getByText(/Smart Route Planning/i)).toBeVisible()

    // No console errors
    expect(errors.length).toBe(0)
  })

  test("features page loads", async ({ page }) => {
    await page.goto("/features")
    await expect(page.getByRole("heading", { name: /Autonomous Logistics Workflows/i })).toBeVisible()
    // No 500-style content
    await expect(page.getByText(/internal server error/i)).not.toBeVisible()
  })

  test("pricing page loads with plan sections", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByRole("heading", { name: /Simple, Transparent Pricing/i })).toBeVisible()
    await expect(page.getByText("Coming Soon")).toBeVisible()
    await expect(page.getByText("Pricing FAQ")).toBeVisible()
  })

  test("download page loads", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("heading", { name: /Download Operion Desktop/i })).toBeVisible()
    // The page renders both Android and iOS CTAs — assert the first one (avoid
    // strict-mode violation from multiple matches).
    await expect(page.getByRole("link", { name: /Download for (Android|iOS)/i }).first()).toBeVisible()
  })

  test("about page loads", async ({ page }) => {
    await page.goto("/about")
    await expect(page.getByRole("heading", { name: /About Operion/i })).toBeVisible()
  })

  test("mission page loads", async ({ page }) => {
    await page.goto("/mission")
    await expect(page.getByRole("heading", { name: /Our Mission/i })).toBeVisible()
  })

  test("FAQ page loads with accordion", async ({ page }) => {
    await page.goto("/faq")
    await expect(page.getByText(/What is Operion/i)).toBeVisible()
  })

  test("contact page loads with form", async ({ page }) => {
    await page.goto("/contact")
    await expect(page.getByRole("heading", { name: /Get in Touch/i })).toBeVisible()
    await expect(page.locator("input#name, input[placeholder*='Name']").first()).toBeVisible()
    await expect(page.locator("input#email, input[type='email']").first()).toBeVisible()
    await expect(page.locator("textarea#message, textarea").first()).toBeVisible()
  })

  test("privacy page loads", async ({ page }) => {
    await page.goto("/privacy")
    // TOC anchor link + section heading both contain the text — scope to heading.
    await expect(page.getByRole("heading", { name: /Information We Collect/i })).toBeVisible()
  })

  test("terms page loads", async ({ page }) => {
    await page.goto("/terms")
    await expect(page.getByRole("heading", { name: /Acceptance of Terms/i })).toBeVisible()
  })

  test("blog page loads", async ({ page }) => {
    await page.goto("/blog")
    await expect(page.getByRole("heading", { name: /Blog/i })).toBeVisible()
  })

  test("docs home loads", async ({ page }) => {
    await page.goto("/docs")
    // Sidebar nav + page heading both contain the text — use a heading role.
    await expect(page.getByRole("heading", { name: /Getting Started/i }).first()).toBeVisible()
  })

  test("waitlist page loads", async ({ page }) => {
    await page.goto("/waitlist")
    await expect(page.locator("#company_name")).toBeVisible()
    await expect(page.locator("#email")).toBeVisible()
  })

  test("404 page shows for unknown routes", async ({ page }) => {
    await page.goto("/nonexistent-page")
    await expect(page.getByText("404")).toBeVisible()
    // getByText also hits the <title> — scope to the h1 heading.
    await expect(page.getByRole("heading", { name: /page not found/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /go home/i })).toBeVisible()
  })

  test("V3 routes load without errors", async ({ page }) => {
    const v3Routes = [
      { path: "/products", heading: /autonomous logistics operating system/i },
      { path: "/integrations", heading: /^integrations$/i },
      { path: "/community", heading: /^community$/i },
      { path: "/enterprise", heading: /enterprise fleets/i },
      { path: "/partners", heading: /partner with operion/i },
      { path: "/trust", heading: /trust center/i },
      { path: "/security", heading: /security at operion/i },
      { path: "/developers", heading: /developer resources/i },
    ]

    for (const { path, heading } of v3Routes) {
      await page.goto(path)
      // .first() — the H1 (exact) is the page title; broader sub-headings may
      // also match the same words, so never rely on a single match.
      await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible()
      // No 500 errors
      await expect(page.getByText(/internal server error/i)).not.toBeVisible()
    }
  })

  test("industry pages load", async ({ page }) => {
    const industryPages = [
      "/industries/transport",
      "/industries/freight",
      "/industries/fleet",
      "/industries/owner-operators",
    ]
    for (const path of industryPages) {
      await page.goto(path)
      // Should not see 500 page or "not found" page
      await expect(page.getByText("404")).not.toBeVisible()
      await expect(page.getByText(/internal server error/i)).not.toBeVisible()
      // Page has some visible content
      await expect(page.locator("main")).toBeVisible()
    }
  })
})
