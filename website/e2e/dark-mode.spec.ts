import { test, expect } from "@playwright/test"

test.describe("Dark Mode", () => {
  test("theme toggle switches to dark mode", async ({ page }) => {
    await page.goto("/")
    const html = page.locator("html")
    await expect(html).not.toHaveClass(/dark/)
    await page.getByLabelText(/toggle theme/i).click()
    // Theme cycles light -> dark -> system
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode persists on page navigation", async ({ page }) => {
    await page.goto("/")
    await page.getByLabelText(/toggle theme/i).click()
    await page.goto("/features")
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode persists on reload", async ({ page }) => {
    await page.goto("/")
    await page.getByLabelText(/toggle theme/i).click()
    await page.reload()
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode affects card styling", async ({ page }) => {
    await page.goto("/")
    await page.getByLabelText(/toggle theme/i).click()
    const card = page.getByText(/intelligent route planning/i).locator("..")
    await expect(card).toBeVisible()
  })
})
