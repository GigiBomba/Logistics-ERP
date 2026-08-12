import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "../helpers"

/**
 * MFA Cycle Tests
 *
 * Tests the full multi-factor authentication flow via mocked API:
 *   1. Login with credentials → API responds mfa_required + mfa_session_token
 *   2. Redirect to /auth/mfa-challenge
 *   3. Submit a TOTP code → mock /api/v1/auth/mfa/verify → dashboard
 *   4. Backup-code path: toggle "Use a backup code instead" → verify → dashboard
 *
 * Uses page.route API mocking + no real backend. Matches the actual UI flow in
 * `src/pages/auth/mfa-challenge.tsx` (TOTP input + backup-code toggle).
 *
 * NOTE: Enroll (settings page 2FA tab) is covered as a follow-up — the settings
 * rebuild is in-flight, so selectors may not be stable yet.
 */

const MOCK_USER = {
  user: {
    id: "2",
    email: "user@operionerp.xyz",
    name: "Regular User",
    role: "user",
    email_verified: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
}

const TOKEN_RESPONSE = {
  access_token: "mock-access-token",
  refresh_token: "mock-refresh-token",
  token_type: "bearer",
  expires_in: 3600,
}

test.describe("MFA Cycle", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
    // Ensure clean auth state. Access tokens live in memory; the refresh token
    // is an httpOnly cookie (never persisted to localStorage/sessionStorage),
    // so we seed the cookie for the cookie-only refresh flow instead.
    // NOTE: no localStorage evaluate here — about:blank has an opaque origin
    // and throws SecurityError; the provider clears legacy keys itself anyway.
    await page.context().addCookies([
      { name: "refresh_token", value: "mock-refresh", domain: "localhost", path: "/api/v1/auth", httpOnly: true },
    ])
  })

  /**
   * Shared route mocks for a full MFA login cycle.
   */
  async function mockMfaFlow(page: import("@playwright/test").Page) {
    // Step 1: login POST → mfa_required
    await page.route("**/api/v1/auth/token", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue()
        return
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...TOKEN_RESPONSE,
          mfa_required: true,
          mfa_session_token: "mfa-session-token-123",
        }),
      })
    })

    // Step 2: MFA verify POST (TOTP or backup code) → full tokens
    await page.route("**/api/v1/auth/mfa/verify", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(TOKEN_RESPONSE),
      })
    })

    // Backup-code endpoint (same response shape) — used if the frontend switches
    // to a dedicated endpoint; currently the challenge page routes both through
    // /auth/mfa/verify, so this is defensive.
    await page.route("**/api/v1/auth/mfa/backup-code", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(TOKEN_RESPONSE),
      })
    })

    // Step 3: after verify, the provider fetches the full profile
    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_USER),
      })
    })
  }

  test("full TOTP MFA cycle: login → challenge → verify → dashboard", async ({ page }) => {
    await mockMfaFlow(page)

    // ─── Step 1: login ────────────────────────────────────────
    await page.goto("/login")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible()

    await page.fill("#email", "user@operionerp.xyz")
    await page.fill("#password", "TestPass123!")
    await page.getByRole("button", { name: /sign in/i }).click()

    // ─── Step 2: redirect to MFA challenge ────────────────────
    await expect(page).toHaveURL(/\/auth\/mfa-challenge/, { timeout: 15000 })
    await expect(page.getByRole("heading", { name: /two-factor authentication/i })).toBeVisible()
    await expect(page.getByText(/enter the verification code/i)).toBeVisible()

    // ─── Step 3: enter TOTP code (auto-submits at 6 digits) ──
    await page.fill("#mfa-code", "123456")

    // ─── Step 4: lands on dashboard ───────────────────────────
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })
    // The dashboard is a heavy client-rendered route (SPA fallback): the router
    // updates the URL before the route chunk loads + hydrates. Under parallel
    // workers the shell can hydrate while the main content still shows the SSR
    // "Loading..." placeholder, so wait for hydration AND for real content to
    // replace that placeholder before asserting.
    await waitForHydration(page)
    await page.waitForFunction(
      () => {
        const main = document.querySelector("main")
        if (!main || main.textContent === null) return false
        const loading = main.querySelector('[role="status"]')
        return main.textContent.trim().length > 0 && loading === null
      },
      { timeout: 30_000 },
    )
    await expect(page.getByText(/welcome back/i)).toBeVisible()

    // ─── Step 5: no-storage contract ──────────────────────────
    // The access token lives in memory and the refresh token is an httpOnly
    // cookie — neither should ever be persisted to localStorage. Use
    // waitForFunction (retries, tolerant of in-flight navigation) instead of a
    // one-shot evaluate, which can hit a destroyed context during the
    // dashboard navigation.
    await page.waitForFunction(() => {
      const storedKeys = Object.keys(localStorage)
      return !storedKeys.includes("operion-access-token") && !storedKeys.includes("operion-refresh-token")
    })
  })

  test("backup-code path: login → challenge → toggle backup → verify → dashboard", async ({ page }) => {
    await mockMfaFlow(page)

    await page.goto("/login")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible()

    await page.fill("#email", "user@operionerp.xyz")
    await page.fill("#password", "TestPass123!")
    await page.getByRole("button", { name: /sign in/i }).click()

    // ─── MFA challenge ─────────────────────────────────────────
    await expect(page).toHaveURL(/\/auth\/mfa-challenge/, { timeout: 15000 })
    await expect(page.getByRole("heading", { name: /two-factor authentication/i })).toBeVisible()

    // Toggle to backup-code mode
    await page.getByRole("button", { name: /use a backup code instead/i }).click()
    await expect(page.getByText(/enter one of your backup codes to sign in/i)).toBeVisible()

    // Enter the 8-char backup code (still auto-submits at 6 digits)
    await page.fill("#mfa-code", "000000")
    await expect(page.getByRole("button", { name: /verify/i })).toBeVisible()

    // The page auto-submits on 6 digits — wait for the dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })
  })

  test("challenge page redirects to login when no MFA session token exists", async ({ page }) => {
    // No login performed → no mfa_session_token in auth provider
    await page.goto("/auth/mfa-challenge")
    await waitForHydration(page)
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  })
})
