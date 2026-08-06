import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

test.describe("V3 Routes Navigation", () => {
  test.beforeEach(async ({ page }) => {
    // Align SSR/client render (cookie consent + offline banner) so the footer
    // and nav interactions are deterministic after hydration.
    stabilizeHydration(page)
  })

  // Headings reflect the CURRENT page H1s (S-grade redesign + i18n sweep).
  // All routes exist at src/routes.tsx:351-437 — verified, no routes added.
  const routes = [
    { path: "/products", heading: /autonomous logistics operating system/i },
    { path: "/integrations", heading: /^integrations$/i },
    { path: "/community", heading: /^community$/i },
    { path: "/customers", heading: /customer stories/i },
    { path: "/careers", heading: /join operion/i },
    { path: "/press", heading: /press & media/i },
    { path: "/brand", heading: /brand guidelines/i },
    { path: "/enterprise", heading: /enterprise fleets/i },
    { path: "/partners", heading: /partner with operion/i },
    { path: "/trust", heading: /trust center/i },
    { path: "/newsletter", heading: /stay updated/i },
  ]

  for (const { path, heading } of routes) {
    test(`${path} page loads with expected heading`, async ({ page }) => {
      await page.goto(path)
      // .first() — broader sub-headings may repeat the same words.
      await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible()
    })
  }

  test("home page links to products page", async ({ page }) => {
    await page.goto("/")
    await waitForHydration(page)
    await page.locator("footer").getByRole("link", { name: "Products" }).click()
    await expect(page).toHaveURL(/\/products/)
    await expect(page.getByRole("heading", { name: /autonomous logistics operating system/i })).toBeVisible()
  })

  test("navigates between products and integrations", async ({ page }) => {
    await page.goto("/products")
    await expect(page.getByRole("heading", { name: /autonomous logistics operating system/i })).toBeVisible()
    await page.goto("/integrations")
    await expect(page.getByRole("heading", { name: /^integrations$/i })).toBeVisible()
  })

  test("footer has v3 route links", async ({ page }) => {
    await page.goto("/")
    await waitForHydration(page)
    const footer = page.locator("footer")
    await expect(footer.getByRole("link", { name: "Products" })).toBeVisible()
    await expect(footer.getByRole("link", { name: "Enterprise" })).toBeVisible()
    await expect(footer.getByRole("link", { name: "Trust Center" })).toBeVisible()
  })
})
