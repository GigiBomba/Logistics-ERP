import { test, expect } from "@playwright/test"
import { waitForHydration } from "../helpers"

test.describe("Chaos — Offline & Edge Cases", () => {
  test("already loaded page remains usable offline", async ({ page }) => {
    await page.goto("/")
    // Hydrate fully before going offline — the home route is lazy-loaded and
    // would otherwise fail to fetch its chunk once the network is cut.
    await waitForHydration(page)
    await page.context().setOffline(true)
    await expect(page.getByRole("heading", { name: /the complete logistics operating system/i })).toBeVisible()
    await expect(page.getByText(/smart route planning/i)).toBeVisible()
  })

  test("navigation to visited cached pages works offline", async ({ page }) => {
    await page.goto("/features")
    // Let the /features chunk load + hydrate before cutting the network — the
    // page's "Route Planning" mockup text only exists after hydration.
    await waitForHydration(page)
    await page.context().setOffline(true)
    // Exact text — /route planning/i also matched the ARGO integrations copy
    // in the AI section (strict-mode violation).
    await expect(page.getByText("Route Planning", { exact: true })).toBeVisible()
  })

  test("handles rapid route changes without error", async ({ page }) => {
    await page.goto("/")
    const pages = ["/", "/features", "/pricing", "/download", "/about", "/mission", "/faq", "/contact"]
    for (const route of pages) {
      await page.goto(route, { waitUntil: "commit" })
    }
    await page.waitForTimeout(1000)
    // Last visited page is /contact — assert its current h1 ("Get in Touch").
    // getByText("Contact") was ambiguous (nav + footer links, contact emails).
    await expect(page.getByRole("heading", { name: /get in touch/i })).toBeVisible()
  })

  test("handles localStorage with invalid token", async ({ page }) => {
    // Seed via addInitScript so it runs on the real origin at navigation
    // (page.evaluate before goto would run on about:blank → SecurityError).
    // The provider removes the legacy token anyway; the redirect to /login is
    // driven by the failing cookie-refresh bootstrap.
    await page.addInitScript(() => {
      localStorage.setItem("operion-access-token", "invalid-not-a-real-token-%%%")
    })
    await page.goto("/dashboard")
    // Should gracefully redirect to login
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  })
})
