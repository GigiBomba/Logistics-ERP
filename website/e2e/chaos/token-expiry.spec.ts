import { test, expect } from "@playwright/test"

test.describe("Chaos — Token Expiry & Refresh", () => {
  const VALID_TOKEN = "valid-token"
  const REFRESH_TOKEN = "refresh-token"

  test.beforeEach(async ({ page }) => {
    // Seed tokens via addInitScript — it runs on the real origin once the page
    // navigates, instead of page.evaluate on about:blank (SecurityError). The
    // provider deletes these legacy keys on mount anyway; the real auth
    // bootstrap (cookie refresh + /me) is mocked per test below.
    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("operion-access-token", accessToken)
      localStorage.setItem("operion-refresh-token", refreshToken)
    }, { accessToken: VALID_TOKEN, refreshToken: REFRESH_TOKEN })
  })

  test("token refresh on 401 works", async ({ page }) => {
    let callCount = 0

    // Catch-all keeps app-shell data requests deterministic (200 []) so only
    // the auth endpoints drive redirect behavior — see
    // e2e/critical/returnurl-redirect.spec.ts. The real bootstrap endpoints are
    // /api/v1/auth/refresh + /api/v1/auth/me (the old /api/auth/* globs never
    // matched and let the test hit the real proxy).
    await page.route("**/api/v1/**", async (route) => {
      const url = route.request().url()
      if (url.includes("/api/v1/auth/refresh") || url.includes("/api/v1/auth/me")) {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })

    await page.route("**/api/v1/auth/me", (route) => {
      callCount++
      if (callCount === 1) {
        route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Token expired" }) })
      } else {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { id: "1", email: "test@c.com", role: "driver", is_admin: false, name: "Test User", email_verified: true, created_at: "", updated_at: "" } }) })
      }
    })

    await page.route("**/api/v1/auth/refresh", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: "new-token", refresh_token: "new-refresh", token_type: "bearer", expires_in: 3600 }) })
    )

    await page.goto("/dashboard", { waitUntil: "networkidle" })
    await expect(page).not.toHaveURL(/\/login/)
  })

  test("failing refresh redirects to login", async ({ page }) => {
    // Mirror the first test's mock topology: the catch-all keeps app-shell
    // data requests deterministic (200 []) while the real bootstrap endpoints
    // (/api/v1/auth/*) drive the redirect. The old /api/auth/* globs never
    // matched the proxy and the .catch(() => {}) swallowed the networkidle
    // timeout — this test previously passed vacuously with zero assertions.
    await page.route("**/api/v1/**", async (route) => {
      const url = route.request().url()
      if (url.includes("/api/v1/auth/refresh") || url.includes("/api/v1/auth/me")) {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })

    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Expired" }) })
    )
    await page.route("**/api/v1/auth/refresh", (route) =>
      route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Refresh token expired" }) })
    )

    await page.goto("/dashboard", { waitUntil: "networkidle" })
    await expect(page).toHaveURL(/\/login/)
  })
})
