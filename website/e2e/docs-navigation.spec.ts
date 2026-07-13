import { test, expect } from "@playwright/test"

test.describe("Docs Navigation", () => {
  test("docs home shows all categories", async ({ page }) => {
    await page.goto("/docs")
    await expect(page.getByText("Getting Started")).toBeVisible()
    await expect(page.getByText("Route Planning")).toBeVisible()
    await expect(page.getByText("Fleet Tracking")).toBeVisible()
    await expect(page.getByText("Dispatch")).toBeVisible()
    await expect(page.getByText("OCR & Documents")).toBeVisible()
    await expect(page.getByText("Analytics")).toBeVisible()
    await expect(page.getByText("Administration")).toBeVisible()
    await expect(page.getByText("API Reference")).toBeVisible()
    await expect(page.getByText("5 articles")).toBeVisible()
    await expect(page.getByText("4 articles")).toBeVisible()
  })

  test("category page lists articles", async ({ page }) => {
    await page.goto("/docs/getting-started")
    await expect(page.getByText("Getting Started")).toBeVisible()
    await expect(page.getByText("Installing Operion ERP")).toBeVisible()
    await expect(page.getByText("Creating Your Account")).toBeVisible()
    await expect(page.getByText("System Requirements")).toBeVisible()
    await expect(page.getByText("Quick Start Guide")).toBeVisible()
  })

  test("article page renders content", async ({ page }) => {
    await page.goto("/docs/getting-started/installation")
    await expect(page.getByText("Installing Operion ERP")).toBeVisible()
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
    await expect(page.getByText(/category not found/i)).toBeVisible()
  })

  test("unknown article shows not found", async ({ page }) => {
    await page.goto("/docs/getting-started/nonexistent")
    await expect(page.getByText(/article not found/i)).toBeVisible()
  })

  test("sidebar navigation works on desktop", async ({ page }) => {
    await page.goto("/docs")
    await page.getByText("Route Planning").click()
    await expect(page).toHaveURL(/\/route-planning/)
    await expect(page.getByText("Creating Your First Route")).toBeVisible()
  })
})
