import { test, expect } from "@playwright/test"

test.describe("Public Navigation", () => {
  test("home page loads with all sections", async ({ page }) => {
    await page.goto("/")
    await expect(page).toHaveTitle(/Operion ERP/)
    await expect(page.getByRole("heading", { name: /enterprise logistics/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /start free trial/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /see how it works/i })).toBeVisible()
    await expect(page.getByText(/intelligent route planning/i)).toBeVisible()
    await expect(page.getByText(/trusted by logistics leaders/i)).toBeVisible()
    await expect(page.getByText(/our mission/i)).toBeVisible()
    await expect(page.getByText(/ready to transform/i)).toBeVisible()
  })

  test("navbar navigates between pages", async ({ page }) => {
    await page.goto("/")
    await page.getByRole("link", { name: "Features" }).click()
    await expect(page).toHaveURL(/\/features/)
    await expect(page.getByRole("heading", { name: /powerful features/i })).toBeVisible()
  })

  test("features page has feature sections", async ({ page }) => {
    await page.goto("/features")
    await expect(page.getByText(/route planning/i)).toBeVisible()
    await expect(page.getByText(/fleet management/i)).toBeVisible()
    await expect(page.getByText(/dispatch & operations/i)).toBeVisible()
    await expect(page.getByText(/document management/i)).toBeVisible()
  })

  test("pricing page has plan cards and toggle", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByText("Starter")).toBeVisible()
    await expect(page.getByText("Professional")).toBeVisible()
    await expect(page.getByText("Enterprise")).toBeVisible()
    await expect(page.getByText(/most popular/i)).toBeVisible()
    await expect(page.getByText("Monthly")).toBeVisible()
    await expect(page.getByText("Yearly")).toBeVisible()
  })

  test("pricing toggle switches between monthly and yearly", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByText("€49").first()).toBeVisible()
    await page.getByText("Yearly").click()
    await expect(page.getByText("€39").first()).toBeVisible()
  })

  test("download page has download card and requirements", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByText(/download operion desktop/i)).toBeVisible()
    await expect(page.getByText(/system requirements/i)).toBeVisible()
    await expect(page.getByRole("link", { name: /download for windows/i })).toBeVisible()
  })

  test("about page loads", async ({ page }) => {
    await page.goto("/about")
    await expect(page.getByRole("heading", { name: /about operion/i })).toBeVisible()
    await expect(page.getByText(/our story/i)).toBeVisible()
    await expect(page.getByText(/our values/i)).toBeVisible()
  })

  test("mission page loads", async ({ page }) => {
    await page.goto("/mission")
    await expect(page.getByRole("heading", { name: /our mission/i })).toBeVisible()
    await expect(page.getByText(/what we believe/i)).toBeVisible()
  })

  test("FAQ page accordion works", async ({ page }) => {
    await page.goto("/faq")
    await expect(page.getByText(/what is operion erp/i)).toBeVisible()
    await page.getByText(/what is operion erp/i).click()
    await expect(page.getByText(/operion erp is a comprehensive/i)).toBeVisible()
  })

  test("contact page has form", async ({ page }) => {
    await page.goto("/contact")
    await expect(page.getByRole("heading", { name: /get in touch/i })).toBeVisible()
    await expect(page.getByLabelText("Name")).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByLabelText("Subject")).toBeVisible()
    await expect(page.getByLabelText("Message")).toBeVisible()
    await expect(page.getByRole("button", { name: /send message/i })).toBeVisible()
  })

  test("privacy page has sections", async ({ page }) => {
    await page.goto("/privacy")
    await expect(page.getByText(/table of contents/i)).toBeVisible()
    await expect(page.getByText(/information we collect/i)).toBeVisible()
  })

  test("terms page has sections", async ({ page }) => {
    await page.goto("/terms")
    await expect(page.getByText(/table of contents/i)).toBeVisible()
    await expect(page.getByText(/acceptance of terms/i)).toBeVisible()
  })

  test("404 page shows for unknown routes", async ({ page }) => {
    await page.goto("/nonexistent-page")
    await expect(page.getByText("404")).toBeVisible()
    await expect(page.getByText(/page not found/i)).toBeVisible()
    await expect(page.getByRole("link", { name: /go home/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /contact support/i })).toBeVisible()
  })

  test("footer links are present", async ({ page }) => {
    await page.goto("/")
    await page.getByText("Features").last().scrollIntoViewIfNeeded()
    await expect(page.getByText("Privacy")).toBeVisible()
    await expect(page.getByText("Terms")).toBeVisible()
  })
})
