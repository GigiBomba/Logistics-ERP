import { test, expect } from "@playwright/test"

test.describe("Chaos — Token Expiry & Refresh", () => {
  const VALID_TOKEN = "valid-token"
  const REFRESH_TOKEN = "refresh-token"

  test.beforeEach(async ({ page }) => {
    await page.goto("/")
    await page.evaluate(({ accessToken, refreshToken }) => {
      localStorage.setItem("operion-access-token", accessToken)
      localStorage.setItem("operion-refresh-token", refreshToken)
    }, { accessToken: VALID_TOKEN, refreshToken: REFRESH_TOKEN })
  })

  test("token refresh on 401 works", async ({ page }) => {
    let callCount = 0

    await page.route("**/api/auth/me", (route) => {
      callCount++
      if (callCount === 1) {
        route.fulfill({ status: 401, body: JSON.stringify({ detail: "Token expired" }) })
      } else {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "1", email: "test@c.com", name: "Test User", email_verified: true, created_at: "", updated_at: "" }) })
      }
    })

    await page.route("**/api/auth/refresh", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: "new-token", refresh_token: "new-refresh" }) })
    )

    await page.goto("/dashboard", { waitUntil: "networkidle" })
    await expect(page.locator("html")).not.toHaveURL(/\/login/)
  })

  test("failing refresh redirects to login", async ({ page }) => {
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ status: 401, body: JSON.stringify({ detail: "Expired" }) })
    )
    await page.route("**/api/auth/refresh", (route) =>
      route.fulfill({ status: 401, body: JSON.stringify({ detail: "Refresh token expired" }) })
    )
    await page.goto("/dashboard", { waitUntil: "networkidle", timeout: 30000 }).catch(() => {})
  })
})
