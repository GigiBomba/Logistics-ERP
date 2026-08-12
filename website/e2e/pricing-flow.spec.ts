import { test, expect } from "@playwright/test"

test.describe("Pricing Flow", () => {
  test("pricing page loads with heading and coming soon card", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page).toHaveTitle(/Pricing/)
    await expect(page.getByRole("heading", { name: /simple, transparent pricing/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /coming soon/i })).toBeVisible()
    await expect(page.getByText(/currently in active development/i)).toBeVisible()
    await expect(page.getByRole("link", { name: /sign up for early access/i })).toBeVisible()
  })

  test("early access button links to register", async ({ page }) => {
    await page.goto("/pricing")
    await page.getByRole("link", { name: /sign up for early access/i }).click()
    await expect(page).toHaveURL(/\/register/)
  })

  test("pricing FAQ section is visible", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByRole("heading", { name: /pricing faq/i })).toBeVisible()
  })

  test("FAQ accordion expands on click", async ({ page }) => {
    await page.goto("/pricing")

    // There should be multiple FAQ items (buttons with aria-expanded)
    const faqButtons = page.locator('button[aria-expanded]')
    const count = await faqButtons.count()
    expect(count).toBeGreaterThanOrEqual(4)

    // First FAQ item should be collapsed initially
    await expect(faqButtons.nth(0)).toHaveAttribute("aria-expanded", "false")

    // Click to expand the first FAQ item
    await faqButtons.nth(0).click()
    await expect(faqButtons.nth(0)).toHaveAttribute("aria-expanded", "true")

    // The answer content should now be visible
    const answerPanels = page.locator('[role="region"], .overflow-hidden > div[class]')
    // After clicking, an answer panel with text should appear
    await expect(page.getByText(/operion is in active development/i).first()).toBeVisible()
  })

  test("FAQ accordion collapses when clicked again", async ({ page }) => {
    await page.goto("/pricing")

    const faqButtons = page.locator('button[aria-expanded]')
    await faqButtons.nth(0).click()
    await expect(faqButtons.nth(0)).toHaveAttribute("aria-expanded", "true")

    // Click again to collapse
    await faqButtons.nth(0).click()
    await expect(faqButtons.nth(0)).toHaveAttribute("aria-expanded", "false")
  })

  test("FAQ accordion items toggle independently", async ({ page }) => {
    await page.goto("/pricing")

    const faqButtons = page.locator('button[aria-expanded]')

    // Expand first item
    await faqButtons.nth(0).click()
    await expect(faqButtons.nth(0)).toHaveAttribute("aria-expanded", "true")

    // Expand second item — first should collapse (single open)
    await faqButtons.nth(1).click()
    await expect(faqButtons.nth(1)).toHaveAttribute("aria-expanded", "true")
  })

  test("CTA section is visible at bottom of page", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByRole("heading", { name: /get early access/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /sign up/i }).last()).toBeVisible()
  })
})
