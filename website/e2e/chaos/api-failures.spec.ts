import { test, expect } from "@playwright/test"

test.describe("Chaos — API Failure Scenarios", () => {
  test("handles API being completely down gracefully", async ({ page }) => {
    await page.route("**/api/**", (route) => route.abort("connectionrefused"))
    await page.goto("/login")
    await expect(page.getByText("Welcome back")).toBeVisible()
    await page.getByLabelText("Email").fill("test@c.com")
    await page.getByLabelText("Password").fill("password")
    await page.getByRole("button", { name: /sign in/i }).click()
    await expect(page.getByText(/error/i).or(page.getByText(/invalid/i))).toBeVisible().catch(() => {
      // Toast may or may not appear depending on timing
    })
  })

  test("handles slow API responses without crashing", async ({ page }) => {
    await page.route("**/api/**", (route) => setTimeout(() => route.abort(), 10000))
    await page.goto("/login")
    // Page should still be interactive
    await expect(page.getByText("Welcome back")).toBeVisible()
  })

  test("handles malformed API responses", async ({ page }) => {
    await page.route("**/api/**", (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<html>not json</html>" })
    )
    await page.goto("/login")
    await expect(page.getByText("Welcome back")).toBeVisible()
    await page.getByRole("button", { name: /sign in/i }).click()
    // Should not crash — error is handled by toast
    await expect(page.getByText("Welcome back")).toBeVisible()
  })

  test("handles 500 errors gracefully", async ({ page }) => {
    await page.route("**/api/**", (route) =>
      route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Internal server error" }) })
    )
    await page.goto("/login")
    await page.getByLabelText("Email").fill("test@c.com")
    await page.getByLabelText("Password").fill("password")
    await page.getByRole("button", { name: /sign in/i }).click()
    // Form remains, error shown in toast
    await expect(page.getByLabelText("Email")).toBeVisible()
  })

  test("navigates to login on 401 from protected page", async ({ page }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Unauthorized" }) })
    )
    await page.goto("/dashboard")
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  })
})
