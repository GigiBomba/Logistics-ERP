import { test, expect, type Page } from "@playwright/test"
import { mockAuthAs, mockLoginFlow, createUser, stabilizeHydration, waitForHydration, type MockUser } from "../helpers"

/**
 * Auth Full Cycle
 *
 * register → verify-email → login → dashboard → logout → login again.
 * The backend is fully mocked via page.route (see e2e/helpers.ts). The app's
 * own auth flow is NOT bypassed — we mock the API, the provider still drives
 * state transitions (setAccessToken, /me profile fetch, logout).
 */

test.describe("Auth Full Cycle", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  async function mockLogout(page: Page) {
    await page.route("**/api/v1/auth/logout", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) })
    })
  }

  test("register, login, logout, login again", async ({ page }) => {
    const email = `test-${Date.now()}@operion.dev`
    const password = "TestPass123!"
    const user: MockUser = createUser("user", {
      id: "2",
      email,
      name: "Test User",
    })

    // Session-wide auth: cookie-refresh bootstrap + login + me + logout.
    // Registered BEFORE any goto so they intercept hydration fetches (SSR).
    await mockAuthAs(page, user)
    await mockLoginFlow(page, user)
    await mockLogout(page)
    await page.route("**/api/v1/registration/register", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ access_token: "mock-access-token", user }),
      })
    })

    // ─── Register ──────────────────────────────────────────────
    await page.goto("/register")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /create account/i })).toBeVisible()

    await page.fill("#name", "Test User")
    await page.fill("#email", email)
    await page.fill("#company_name", "Test Company")
    await page.fill("#password", password)
    await page.fill("#confirm_password", password)
    // Check terms — required by the schema (z.literal(true))
    await page.check("#termsAccepted")
    await page.click('button[type="submit"]')

    // Should redirect to verify-email after registration
    await expect(page).toHaveURL(/\/verify-email/, { timeout: 15000 })
    await expect(page.getByText(/check your email/i)).toBeVisible()

    // ─── Login ─────────────────────────────────────────────────
    await page.goto("/login")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible()

    await page.fill("#email", email)
    await page.fill("#password", password)
    await page.click('button[type="submit"]')

    // Should land on dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })

    // ─── Logout ────────────────────────────────────────────────
    // Open the user menu in the dashboard header and sign out through the UI.
    // Scope to the header (banner) — the dashboard sidebar also has a
    // "Sign out" button, so an unscoped locator would be ambiguous.
    await page.getByRole("button", { name: /test user/i }).first().click()
    await page.getByRole("banner").getByRole("button", { name: /sign out/i }).click()

    // Logout clears the session; ProtectedRoute deterministically redirects to
    // /login?returnUrl=/dashboard (designed §9.2 returnUrl flow).
    await expect(page).toHaveURL(/\/login\?returnUrl=/, { timeout: 15000 })

    // ─── Login again ───────────────────────────────────────────
    await page.goto("/login")
    await waitForHydration(page)
    await page.fill("#email", email)
    await page.fill("#password", password)
    await page.click('button[type="submit"]')

    // Should land on dashboard again
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })

    // Verify something on the dashboard rendered (the page heading — there is
    // no literal "dashboard" text on the dashboard itself).
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible()
  })
})
