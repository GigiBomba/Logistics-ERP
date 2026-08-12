import { test, expect } from "@playwright/test"

test.describe("Download Flow", () => {
  test("download page loads with platform options", async ({ page }) => {
    await page.goto("/download")
    await expect(page).toHaveTitle(/Download/)
    await expect(page.getByRole("heading", { name: /operion desktop/i })).toBeVisible()
    await expect(page.getByText(/system requirements/i)).toBeVisible()
  })

  test("release channel tabs are present", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("tab", { name: /stable/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /beta/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /nightly/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /legacy/i })).toBeVisible()
  })

  test("stable tab is active by default", async ({ page }) => {
    await page.goto("/download")
    const stableTab = page.getByRole("tab", { name: /stable/i })
    await expect(stableTab).toHaveAttribute("data-state", "active")
  })

  test("beta tab switches content", async ({ page }) => {
    await page.goto("/download")
    await page.getByRole("tab", { name: /beta/i }).click()
    await expect(page.getByText(/request beta access/i)).toBeVisible()
    await expect(page.getByPlaceholder(/search/i)).toBeVisible()
  })

  test("nightly tab shows warning", async ({ page }) => {
    await page.goto("/download")
    await page.getByRole("tab", { name: /nightly/i }).click()
    await expect(page.getByText(/not recommended for production/i)).toBeVisible()
  })

  test("legacy tab shows previous versions", async ({ page }) => {
    await page.goto("/download")
    await page.getByRole("tab", { name: /legacy/i }).click()
    await expect(page.getByText(/previous versions/i)).toBeVisible()
  })

  test("system requirements section displays hardware specs", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByText(/windows 10.*64-bit/i)).toBeVisible()
    await expect(page.getByText(/intel core i5/i)).toBeVisible()
    await expect(page.getByText(/8 gb minimum/i)).toBeVisible()
  })

  test("installation instructions are present", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("heading", { name: /installation/i })).toBeVisible()
    await expect(page.getByText(/step 1/i)).toBeVisible()
    await expect(page.getByText(/step 2/i)).toBeVisible()
    await expect(page.getByText(/step 3/i)).toBeVisible()
    await expect(page.getByText(/step 4/i)).toBeVisible()
  })

  test("toolkit download link has correct href", async ({ page }) => {
    await page.goto("/download")
    // Scroll to toolkit section
    await page.getByText(/toolkit/i).last().scrollIntoViewIfNeeded()

    const toolkitButtons = page.getByRole("link", { name: /download toolkit/i })
    await expect(toolkitButtons.first()).toBeVisible()
    await expect(toolkitButtons.first()).toHaveAttribute("href", /\/downloads\/operion-toolkit/)
  })

  test("documentation bundle button triggers alert", async ({ page }) => {
    await page.goto("/download")
    await page.getByText(/offline documentation/i).scrollIntoViewIfNeeded()

    // The documentation bundle button should be visible
    await expect(page.getByRole("button", { name: /download docs bundle/i })).toBeVisible()
  })

  test("migration guides section is present", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("heading", { name: /migration guides/i })).toBeVisible()
  })

  test("toolkit section links to documentation page", async ({ page }) => {
    await page.goto("/download")
    await page.getByText(/toolkit/i).last().scrollIntoViewIfNeeded()
    await page.getByRole("link", { name: /documentation/i }).last().click()
    await expect(page).toHaveURL(/\/developers\/toolkit/)
  })
})
