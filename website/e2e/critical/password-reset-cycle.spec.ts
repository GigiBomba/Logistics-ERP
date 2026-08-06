import { test, expect } from "@playwright/test"
import { mockLoginFlow, createUser, stabilizeHydration, waitForHydration } from "../helpers"

/**
 * Password Reset Cycle Tests
 *
 * Tests: forgot password → reset link → new password → login with new password.
 *
 * The reset link is simulated by navigating directly to /reset-password with a
 * token the test controls (no real email capture needed). The backend is fully
 * mocked via page.route (see e2e/helpers.ts) — the app's own reset flow drives
 * the state transitions.
 */

test.describe("Password Reset Cycle", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  test("forgot password page renders and accepts email", async ({ page }) => {
    // Mock the forgot-password POST so the test is deterministic offline.
    await page.route("**/api/v1/auth/forgot-password", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) })
    })

    await page.goto("/forgot-password")
    await expect(page.getByRole("heading", { name: /reset password/i })).toBeVisible()

    await page.fill("#email", "user@operionerp.xyz")
    await page.getByRole("button", { name: /send reset link/i }).click()

    // The form stays put (success toast + no navigation)
    await expect(page.getByRole("heading", { name: /reset password/i })).toBeVisible()
  })

  test("reset-password without token shows invalid link message", async ({ page }) => {
    await page.goto("/reset-password")
    // When no token is present, the page renders "Invalid Reset Link"
    await expect(page.getByText(/invalid reset link|invalid link/i)).toBeVisible()
    // There should be a button to request a new link
    await expect(page.getByRole("link", { name: /request new link/i })).toBeVisible()
  })

  test("reset-password with token shows form and validates", async ({ page }) => {
    // Navigate with a fake token
    await page.goto("/reset-password?token=fake-test-token-123")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /set new password/i })).toBeVisible()

    // The form should be visible
    await expect(page.locator("#password")).toBeVisible()
    await expect(page.locator("#confirm_password")).toBeVisible()

    // Try submitting with mismatched passwords
    await page.fill("#password", "NewPass123!")
    await page.fill("#confirm_password", "DifferentPass1!")
    await page.getByRole("button", { name: /reset password/i }).click()

    // Should show validation error about passwords not matching
    await expect(page.getByText(/passwords don't match/i)).toBeVisible()
  })

  test("full password reset cycle — forgot → reset link → set new password → login", async ({ page }) => {
    const email = `reset-${Date.now()}@operionerp.xyz`
    const newPassword = "NewPass123!"

    // (a) Request the reset link — mock the forgot-password POST so the form's
    //     success path fires deterministically.
    await page.route("**/api/v1/auth/forgot-password", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) })
    })
    await page.goto("/forgot-password")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /reset password/i })).toBeVisible()
    await page.fill("#email", email)
    await page.getByRole("button", { name: /send reset link/i }).click()
    // Visible success state: the reset-link toast (the form stays put).
    await expect(page.getByText(/reset link has been sent/i)).toBeVisible()

    // (b) Simulate the emailed link: navigate with a KNOWN token (we control the
    //     value — no email capture needed) and set a new password. Mock the
    //     reset-password POST.
    await page.route("**/api/v1/auth/reset-password", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) })
    })
    await page.goto("/reset-password?token=mock-reset-token-123")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /set new password/i })).toBeVisible()
    await page.fill("#password", newPassword)
    await page.fill("#confirm_password", newPassword)
    await page.getByRole("button", { name: /reset password/i }).click()
    // The reset success path navigates to the login page.
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible()

    // (c) Sign in with the new password via the mocked login flow.
    const user = createUser("user", { id: "2", email, name: "Reset User" })
    await mockLoginFlow(page, user, false)
    await page.goto("/login")
    await waitForHydration(page)
    await page.fill("#email", email)
    await page.fill("#password", newPassword)
    await page.getByRole("button", { name: /sign in/i }).click()
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })
  })
})
