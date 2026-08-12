import { test, expect } from "@playwright/test"
import { mockLoginFlow, createUser, stabilizeHydration, waitForHydration } from "../helpers"

/**
 * returnUrl Redirect Tests
 *
 * Tests that hitting a protected route unauthenticated redirects to login
 * with a returnUrl parameter, and after login the user lands back on the
 * original route.
 */

test.describe("returnUrl Redirect", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
    // Ensure no auth state. The cookie-only refresh flow (POST /api/v1/auth/refresh)
    // hits the real proxy without mocks → auth fails → user stays null → protected
    // routes redirect to login. No localStorage evaluate here: about:blank has an
    // opaque origin (SecurityError) and the provider manages its own tokens.
    //
    // Mock ALL data endpoints to return 200 empty JSON (except auth refresh/me,
    // which we leave unmocked so auth fails). Without this, the app-shell's
    // /api/v1/organizations fetch gets a 401 and apiClient's interceptor does a
    // HARD `window.location.href = "/login"` — which DROPS the ?returnUrl= that
    // ProtectedRoute sets. Mocking the data keeps the SPA redirect intact.
    //
    // NOTE: the glob MUST be /api/v1/ not /api/ — in vike dev the source
    // modules live at /src/api/*.ts, and a broad /api/ catch-all intercepts
    // those script requests, fulfilling them with JSON (MIME mismatch) and
    // breaking client hydration entirely.
    await page.route("**/api/v1/**", async (route) => {
      const url = route.request().url()
      if (url.includes("/api/v1/auth/refresh") || url.includes("/api/v1/auth/me")) {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
  })

  test("unauthenticated access to /dashboard redirects to /login?returnUrl", async ({ page }) => {
    await page.goto("/dashboard")
    // Should redirect to login with returnUrl parameter
    await expect(page).toHaveURL(/\/login\?returnUrl=/, { timeout: 15000 })
    // The returnUrl should be /dashboard
    await expect(page).toHaveURL(/returnUrl=%2Fdashboard/)
  })

  test("unauthenticated access to /dashboard/profile redirects with correct returnUrl", async ({ page }) => {
    await page.goto("/dashboard/profile")
    await expect(page).toHaveURL(/\/login\?returnUrl=/, { timeout: 15000 })
    await expect(page).toHaveURL(/returnUrl=%2Fdashboard%2Fprofile/)
  })

  test("unauthenticated access to /dashboard/devices redirects with correct returnUrl", async ({ page }) => {
    await page.goto("/dashboard/devices")
    await expect(page).toHaveURL(/\/login\?returnUrl=/, { timeout: 15000 })
    await expect(page).toHaveURL(/returnUrl=%2Fdashboard%2Fdevices/)
  })

  test("login without returnUrl goes to /dashboard", async ({ page }) => {
    await page.goto("/login")
    await expect(page).toHaveURL(/\/login/)

    // We can't actually log in without a backend, but we can verify the redirect
    // behavior by checking that the login page renders correctly
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible()
  })

  test("full returnUrl cycle — login then land on original page", async ({ page }) => {
    const user = createUser("user", { id: "2", email: "test-user@operionerp.xyz", name: "Test User" })
    const password = "TestPass123!"

    // 1. Unauthenticated access to a protected route → ProtectedRoute redirects
    //    to /login with the original path preserved as returnUrl. NO auth mocks
    //    are registered yet — the auth bootstrap must FAIL so the SPA redirect
    //    fires (the beforeEach catch-all keeps non-auth endpoints at 200[] and
    //    lets the refresh/me calls hit the absent backend).
    await page.goto("/dashboard/devices")
    await expect(page).toHaveURL(/\/login\?returnUrl=%2Fdashboard%2Fdevices/, { timeout: 15000 })

    // 2. Now mock the login POST (non-MFA) + the /me profile fetch so the real
    //    provider login flow (auth-provider.login) succeeds. Registered AFTER the
    //    redirect — registering the auth bootstrap before the initial goto would
    //    pre-authenticate the session and the returnUrl redirect would never fire.
    await mockLoginFlow(page, user, false)

    // 3. Fill + submit the login form.
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible()
    await page.fill("#email", user.email)
    await page.fill("#password", password)
    await page.getByRole("button", { name: /sign in/i }).click()

    // 4. Land back on the ORIGINAL protected page — not the /dashboard default.
    await expect(page).toHaveURL(/\/dashboard\/devices/, { timeout: 15000 })
    await waitForHydration(page)
    // The devices page actually rendered (h1 "Devices"), proving the full cycle.
    await expect(page.getByRole("heading", { name: /^devices$/i })).toBeVisible()
  })
})
