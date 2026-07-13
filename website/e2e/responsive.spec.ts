import { test, expect } from "@playwright/test"

test.describe("Responsive Design", () => {
  test("mobile nav shows hamburger menu", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await expect(page.getByLabelText(/toggle menu/i)).toBeVisible()
    await expect(page.getByRole("link", { name: "Features" })).not.toBeVisible()
  })

  test("mobile menu opens and shows all nav items", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await page.getByLabelText(/toggle menu/i).click()
    await expect(page.getByRole("link", { name: "Features" })).toBeVisible()
    await expect(page.getByRole("link", { name: "Home" })).toBeVisible()
    await expect(page.getByRole("link", { name: "Pricing" })).toBeVisible()
    await expect(page.getByRole("link", { name: "Download" })).toBeVisible()
    await expect(page.getByRole("link", { name: "About" })).toBeVisible()
    await expect(page.getByRole("link", { name: "Docs" })).toBeVisible()
    await expect(page.getByRole("link", { name: "Contact" })).toBeVisible()
  })

  test("mobile menu closes on nav item click", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await page.getByLabelText(/toggle menu/i).click()
    await page.getByRole("link", { name: "Features" }).click()
    await expect(page).toHaveURL(/\/features/)
  })

  test("desktop nav is fully visible", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto("/")
    await expect(page.getByLabelText(/toggle menu/i)).not.toBeVisible()
    await expect(page.getByRole("link", { name: "Features" })).toBeVisible()
    await expect(page.getByRole("link", { name: "Pricing" })).toBeVisible()
  })

  test("footer stacks on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await page.getByText("Product").last().scrollIntoViewIfNeeded()
    await expect(page.getByText("Product")).toBeVisible()
    await expect(page.getByText("Company")).toBeVisible()
    await expect(page.getByText("Resources")).toBeVisible()
  })
})
