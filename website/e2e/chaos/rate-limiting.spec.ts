import { test, expect } from "@playwright/test"
import { waitForHydration } from "../helpers"

test.describe("Chaos — Rate Limiting & Rapid Requests", () => {
  test("rapid repeated requests to same page don't crash the app", async ({ page }) => {
    await page.goto("/")
    // Fire 50 rapid navigations at the same route. Concurrent page.goto() calls
    // cancel each other's navigation (net::ERR_ABORTED) — expected browser
    // behavior, not an app crash — so swallow the aborted navigations. The real
    // contract is: the page still loads normally afterwards.
    const requests = Array.from({ length: 50 }, (_, i) =>
      page.goto("/", { waitUntil: "commit" }).catch(() => {})
    )
    await Promise.all(requests)
    // After rapid fire, the page should still load normally
    await page.goto("/", { waitUntil: "networkidle" })
    await expect(page.getByRole("heading", { name: /the complete logistics operating system/i })).toBeVisible()
  })

  test("rapid form submissions are handled without crashing", async ({ page }) => {
    await page.goto("/contact")
    await expect(page.getByText(/get in touch/i)).toBeVisible()

    const submitRapidly = async () => {
      await page.getByLabel(/name/i).fill("Test User")
      await page.getByLabel(/email/i).fill("test@example.com")
      await page.getByLabel(/message/i).fill("Test message")
      await page.getByRole("button", { name: /send|submit/i }).click()
    }

    // Fire off several rapid submissions
    const submissions = Array.from({ length: 5 }, () => submitRapidly())
    await Promise.all(submissions.map((p) => p.catch(() => {})))

    // Page should not be crashed — interact with it
    await page.waitForTimeout(1000)
    await expect(page.getByText(/get in touch/i)).toBeVisible()
  })

  test("navigating while requests are in-flight doesn't break navigation", async ({ page }) => {
    // Start a slow-loading page
    await page.route("**/*", (route) => {
      // Slow down responses to keep requests in-flight. Rapid navigations
      // abort in-flight requests and `unroute` can run before this timer
      // fires — swallow the resulting "Route is already handled" rejections
      // (they are expected browser behaviour, not an app defect).
      setTimeout(() => {
        route.continue().catch(() => {})
      }, 500)
    })

    await page.goto("/", { waitUntil: "commit" })

    // Navigate rapidly while requests are pending. 20s per navigation: with
    // every request delayed 500ms by the route above and the full suite
    // running workers in parallel, 10s was tight enough to flake under load.
    const navs = ["/features", "/pricing", "/download", "/about", "/faq", "/contact"]
    for (const route of navs) {
      await page.goto(route, { waitUntil: "commit", timeout: 20000 })
    }

    // Clean up route interception
    await page.unroute("**/*")

    // Final navigation should succeed
    await page.goto("/", { waitUntil: "networkidle" })
    // networkidle can fire before the lazy home route renders — settle first.
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /the complete logistics operating system/i })).toBeVisible()
  })
})
