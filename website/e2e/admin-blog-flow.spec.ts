import { test, expect } from "@playwright/test"
import { mockAuthAs, createUser, stabilizeHydration, type MockUser } from "./helpers"

test.describe("Admin Blog Flow", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  const ADMIN_USER: MockUser = createUser("admin", {
    id: "1",
    email: "admin@operionerp.xyz",
    name: "Admin User",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  })

  const REGULAR_USER: MockUser = createUser("user", {
    id: "2",
    email: "user@operionerp.xyz",
    name: "Regular User",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  })

  test("login page renders correctly", async ({ page }) => {
    await page.goto("/login")
    await expect(page.getByText("Welcome back")).toBeVisible()
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
    await expect(page.getByLabel(/^password$/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible()
  })

  test("admin blog editor route is protected — redirects to /login without auth", async ({ page }) => {
    // No auth mocks → cookie-refresh bootstrap fails → unauthenticated → guard redirects
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
    // Mock categories so the category select renders instead of a loading skeleton
    await page.route("**/api/v1/blog/categories", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
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
    // Mock blog API endpoints to avoid loading issues
    await page.route("**/api/v1/blog/categories", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
    await page.route("**/api/v1/blog/posts*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0 }) })
    })
    await page.goto("/blog")
    await expect(page.getByRole("link", { name: /new article/i })).toBeVisible({ timeout: 15000 })
  })

  test("blog article shows admin control when admin is logged in", async ({ page }) => {
    await mockAuthAs(page, ADMIN_USER)
    // Mock the post detail endpoint so the article page renders (the API is
    // otherwise unreachable from e2e; the app falls back to an in-bundle list).
    await page.route("**/api/v1/blog/posts/getting-started-with-operion", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          title: "Getting Started with Operion",
          slug: "getting-started-with-operion",
          excerpt: "Getting started with Operion.",
          seo_description: "Getting started with Operion.",
          content: "<p>Welcome to Operion.</p>",
          author_name: "Operion Team",
          category: "Getting Started",
          tags: ["getting-started"],
          featured_image: "",
          reading_time_minutes: 3,
          published_at: "2026-01-01T00:00:00Z",
        }),
      })
    })
    await page.goto("/blog/getting-started-with-operion")
    // The current admin control on the article page is the admin-access banner
    // (blog-article.tsx) — the former "Edit Article" button was removed in the
    // S-grade redesign.
    await expect(page.getByText("You have admin access to manage blog content")).toBeVisible({ timeout: 15000 })
  })
})
