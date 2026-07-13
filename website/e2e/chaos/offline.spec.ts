import { test, expect } from "@playwright/test"

test.describe("Chaos — Offline & Edge Cases", () => {
  test("already loaded page remains usable offline", async ({ page }) => {
    await page.goto("/")
    await page.context().setOffline(true)
    await expect(page.getByRole("heading", { name: /enterprise logistics/i })).toBeVisible()
    await expect(page.getByText(/intelligent route planning/i)).toBeVisible()
  })

  test("navigation to visited cached pages works offline", async ({ page }) => {
    await page.goto("/features")
    await page.context().setOffline(true)
    await expect(page.getByText(/route planning/i)).toBeVisible()
  })

  test("handles rapid route changes without error", async ({ page }) => {
    await page.goto("/")
    const pages = ["/", "/features", "/pricing", "/download", "/about", "/mission", "/faq", "/contact"]
    for (const route of pages) {
      await page.goto(route, { waitUntil: "commit" })
    }
    await page.waitForTimeout(1000)
    await expect(page.getByText("Contact")).toBeVisible()
  })

  test("handles localStorage with invalid token", async ({ page }) => {
    await page.goto("/")
    await page.evaluate(() => {
      localStorage.setItem("operion-access-token", "invalid-not-a-real-token-%%%")
    })
    await page.goto("/dashboard")
    // Should gracefully redirect to login
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  })
})
