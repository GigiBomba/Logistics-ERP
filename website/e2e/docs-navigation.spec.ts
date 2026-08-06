import { test, expect } from "@playwright/test"

test.describe("Docs Navigation", () => {
  test("docs home shows all categories", async ({ page }) => {
    await page.goto("/docs")
    // Category cards (h3) duplicate the sidebar labels — scope to heading role.
    await expect(page.getByRole("heading", { name: /getting started/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /route planning/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /fleet tracking/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /^dispatch$/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /ocr & documents/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /analytics/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /administration/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /api reference/i })).toBeVisible()
    // Data-driven article counts (docs-category.tsx: 5 + 4).
    await expect(page.getByText("5 articles")).toBeVisible()
    await expect(page.getByText("4 articles")).toBeVisible()
  })

  test("category page lists articles", async ({ page }) => {
    await page.goto("/docs/getting-started")
    await expect(page.getByRole("heading", { name: /getting started/i })).toBeVisible()
    await expect(page.getByText("Installing Operion ERP")).toBeVisible()
    await expect(page.getByText("Creating Your Account")).toBeVisible()
    await expect(page.getByText("System Requirements")).toBeVisible()
    await expect(page.getByText("Quick Start Guide")).toBeVisible()
  })

  test("article page renders content", async ({ page }) => {
    await page.goto("/docs/getting-started/installation")
    // Title renders in both the breadcrumb and the h1 — scope to heading.
    await expect(page.getByRole("heading", { name: /installing operion erp/i })).toBeVisible()
    await expect(page.getByText(/before you begin/i)).toBeVisible()
    await expect(page.getByText(/download the installer/i)).toBeVisible()
    await expect(page.getByText(/installation steps/i)).toBeVisible()
  })

  test("navigation between docs pages", async ({ page }) => {
    await page.goto("/docs/getting-started")
    await page.getByText("Installing Operion ERP").click()
    await expect(page).toHaveURL(/\/installation/)
    await expect(page.getByText(/before you begin/i)).toBeVisible()
  })

  test("back link on article page", async ({ page }) => {
    await page.goto("/docs/getting-started/installation")
    await page.getByText("Getting Started").first().click()
    await expect(page).toHaveURL(/\/docs\/getting-started$/)
  })

  test("unknown category shows not found", async ({ page }) => {
    await page.goto("/docs/unknown-category")
    await expect(page.getByRole("heading", { name: /category not found/i })).toBeVisible()
  })

  test("unknown article shows not found", async ({ page }) => {
    await page.goto("/docs/getting-started/nonexistent")
    await expect(page.getByRole("heading", { name: /article not found/i })).toBeVisible()
  })

  test("sidebar navigation works on desktop", async ({ page }) => {
    await page.goto("/docs")
    // "Route Planning" appears in both the sidebar and the category card — use the sidebar link.
    await page.locator("aside").getByRole("link", { name: /route planning/i }).click()
    await expect(page).toHaveURL(/\/route-planning/)
    await expect(page.getByText("Creating Your First Route")).toBeVisible()
  })
})
