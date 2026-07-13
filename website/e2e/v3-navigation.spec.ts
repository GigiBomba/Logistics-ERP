import { test, expect } from "@playwright/test"

test.describe("V3 Routes Navigation", () => {
  const routes = [
    { path: "/products", heading: /all products|products/i },
    { path: "/integrations", heading: /integrations/i },
    { path: "/community", heading: /community/i },
    { path: "/customers", heading: /customer stories/i },
    { path: "/careers", heading: /careers/i },
    { path: "/press", heading: /press/i },
    { path: "/brand", heading: /brand assets/i },
    { path: "/enterprise", heading: /enterprise/i },
    { path: "/partners", heading: /partners/i },
    { path: "/trust", heading: /trust.*security/i },
    { path: "/newsletter", heading: /stay updated/i },
  ]

  for (const { path, heading } of routes) {
    test(`${path} page loads with expected heading`, async ({ page }) => {
      await page.goto(path)
      await expect(page.getByRole("heading", { name: heading })).toBeVisible()
    })
  }

  test("home page links to products page", async ({ page }) => {
    await page.goto("/")
    await page.getByRole("link", { name: /products/i }).first().click()
    await expect(page).toHaveURL(/\/products/)
    await expect(page.getByRole("heading", { name: /all products/i })).toBeVisible()
  })

  test("navigates between products and integrations", async ({ page }) => {
    await page.goto("/products")
    await expect(page.getByRole("heading", { name: /all products/i })).toBeVisible()
    await page.goto("/integrations")
    await expect(page.getByRole("heading", { name: /integrations/i })).toBeVisible()
  })

  test("footer has v3 route links", async ({ page }) => {
    await page.goto("/")
    await page.getByText("Products").last().scrollIntoViewIfNeeded()
    await expect(page.getByText("Products")).toBeVisible()
    await expect(page.getByText("Integrations")).toBeVisible()
    await expect(page.getByText("Community")).toBeVisible()
  })
})
