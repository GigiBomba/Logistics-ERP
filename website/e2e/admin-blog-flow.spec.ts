import { test, expect } from "@playwright/test"

test.describe("Admin Blog Flow", () => {
  const ADMIN_USER = {
    id: "1",
    email: "admin@operion.com",
    name: "Admin User",
    role: "admin",
    email_verified: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  }

  const REGULAR_USER = {
    id: "2",
    email: "user@operion.com",
    name: "Regular User",
    role: "user",
    email_verified: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  }

  async function mockAuthAs(page, user) {
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(user),
      })
    })
    await page.evaluate(() => {
      localStorage.setItem("operion-access-token", "mock-token")
    })
  }

  async function clearAuth(page) {
    await page.evaluate(() => {
      localStorage.removeItem("operion-access-token")
    })
  }

  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login")
    await expect(page.getByText("Welcome back")).toBeVisible()
    await expect(page.getByLabelText("Email")).toBeVisible()
    await expect(page.getByLabelText("Password")).toBeVisible()
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible()
  })

  test("admin blog editor route is protected — redirects to /login without auth", async ({ page }) => {
    await clearAuth(page)
    await page.goto("/admin/blog/editor")
    await expect(page).toHaveURL(/\/login/)
  })

  test("admin blog editor route redirects non-admin users to /dashboard", async ({ page }) => {
    await mockAuthAs(page, REGULAR_USER)
    await page.goto("/admin/blog/editor")
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })
  })

  test("admin blog editor page loads for admin", async ({ page }) => {
    await mockAuthAs(page, ADMIN_USER)
    await page.goto("/admin/blog/editor")
    await expect(page.getByRole("heading", { name: /new article/i })).toBeVisible({ timeout: 15000 })
    await expect(page).toHaveURL(/\/admin\/blog\/editor/)
  })

  test("blog editor form fields are present when loaded as admin", async ({ page }) => {
    await mockAuthAs(page, ADMIN_USER)
    await page.goto("/admin/blog/editor")
    await expect(page.getByRole("heading", { name: /new article/i })).toBeVisible({ timeout: 15000 })

    // Main form fields
    await expect(page.locator("#title")).toBeVisible()
    await expect(page.locator("#slug")).toBeVisible()
    await expect(page.locator("#excerpt")).toBeVisible()
    await expect(page.locator("#content")).toBeVisible()

    // Sidebar fields
    await expect(page.locator("#category")).toBeVisible()
    await expect(page.getByPlaceholder(/fleet, logistics/i)).toBeVisible()
    await expect(page.getByPlaceholder(/https:\/\//i)).toBeVisible()

    // Publish buttons
    await expect(page.getByRole("button", { name: /save draft/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /^publish$/i })).toBeVisible()
  })

  test("blog editor shows preview tab", async ({ page }) => {
    await mockAuthAs(page, ADMIN_USER)
    await page.goto("/admin/blog/editor")
    await expect(page.getByRole("heading", { name: /new article/i })).toBeVisible({ timeout: 15000 })

    // Preview tab should exist
    const previewTrigger = page.getByRole("tab", { name: /preview/i })
    await expect(previewTrigger).toBeVisible()

    // Click preview tab
    await previewTrigger.click()
    await expect(page.getByText(/start writing to see a preview/i)).toBeVisible()
  })

  test("blog list shows 'New Article' admin button when admin is logged in", async ({ page }) => {
    await mockAuthAs(page, ADMIN_USER)
    // Mock categories API to avoid loading issues
    await page.route("**/api/blog/categories", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
    await page.route("**/api/blog/posts*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
    await page.goto("/blog")
    await expect(page.locator("text=New Article")).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole("link", { name: /new article/i })).toBeVisible()
  })

  test("blog article shows 'Edit Article' admin button when admin is logged in", async ({ page }) => {
    await mockAuthAs(page, ADMIN_USER)
    await page.goto("/blog/getting-started-with-operion")
    await expect(page.getByRole("button", { name: /edit article/i })).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole("link", { name: /edit article/i })).toBeVisible()
  })
})
