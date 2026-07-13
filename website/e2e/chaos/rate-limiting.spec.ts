import { test, expect } from "@playwright/test"

test.describe("Chaos — Rate Limiting & Rapid Requests", () => {
  test("rapid repeated requests to same page don't crash the app", async ({ page }) => {
    await page.goto("/")
    const requests = Array.from({ length: 50 }, (_, i) => page.goto("/", { waitUntil: "commit" }))
    await Promise.all(requests)
    // After rapid fire, the page should still load normally
    await page.goto("/", { waitUntil: "networkidle" })
    await expect(page.getByRole("heading", { name: /enterprise logistics/i })).toBeVisible()
  })

  test("rapid form submissions are handled without crashing", async ({ page }) => {
    await page.goto("/contact")
    await expect(page.getByText(/get in touch/i)).toBeVisible()

    const submitRapidly = async () => {
      await page.getByLabelText(/name/i).fill("Test User")
      await page.getByLabelText(/email/i).fill("test@example.com")
      await page.getByLabelText(/message/i).fill("Test message")
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
      // Slow down responses to keep requests in-flight
      setTimeout(() => route.continue(), 500)
    })

    await page.goto("/", { waitUntil: "commit" })

    // Navigate rapidly while requests are pending
    const navs = ["/features", "/pricing", "/download", "/about", "/faq", "/contact"]
    for (const route of navs) {
      await page.goto(route, { waitUntil: "commit", timeout: 10000 })
    }

    // Clean up route interception
    await page.unroute("**/*")

    // Final navigation should succeed
    await page.goto("/", { waitUntil: "networkidle" })
    await expect(page.getByRole("heading", { name: /enterprise logistics/i })).toBeVisible()
  })
})
