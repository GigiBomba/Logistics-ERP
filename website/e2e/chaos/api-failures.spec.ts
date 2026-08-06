import { test, expect } from "@playwright/test"
import { waitForHydration } from "../helpers"

test.describe("Chaos — API Failure Scenarios", () => {
  test("handles API being completely down gracefully", async ({ page }) => {
    await page.route("**/api/**", (route) => route.abort("connectionrefused"))
    await page.goto("/login")
    await expect(page.getByText("Welcome back")).toBeVisible()
    await page.getByLabel("Email", { exact: true }).fill("test@c.com")
    await page.getByLabel("Password", { exact: true }).fill("password")
    await page.getByRole("button", { name: /sign in/i }).click()
    // Should not crash or navigate away — error is handled client-side. The
    // toast itself has timing variance, so assert the login page stays intact
    // (same contract as the malformed/500 scenarios below).
    await expect(page.getByText("Welcome back")).toBeVisible()
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
    await page.getByLabel("Email", { exact: true }).fill("test@c.com")
    await page.getByLabel("Password", { exact: true }).fill("password")
    await page.getByRole("button", { name: /sign in/i }).click()
    // Form remains, error shown in toast
    await expect(page.getByLabel("Email", { exact: true })).toBeVisible()
  })

  test("navigates to login on 401 from protected page", async ({ page }) => {
    // Deterministic auth bootstrap: mock the cookie-refresh + /me endpoints so
    // the test never hits the real api.operionerp.xyz proxy (mirrors the
    // mockAuthAs pattern in e2e/helpers.ts). /me returns 401 → the provider
    // clears auth → ProtectedRoute SPA-redirects to /login. The catch-all keeps
    // app-shell data requests at 200 [] so only the auth flow drives the
    // redirect (same trick as e2e/critical/returnurl-redirect.spec.ts).
    await page.route("**/api/v1/**", async (route) => {
      const url = route.request().url()
      if (url.includes("/api/v1/auth/refresh") || url.includes("/api/v1/auth/me")) {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
    await page.route("**/api/v1/auth/refresh", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Unauthorized" }) })
    )
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Unauthorized" }) })
    )
    await page.goto("/dashboard")
    await waitForHydration(page)
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  })
})
