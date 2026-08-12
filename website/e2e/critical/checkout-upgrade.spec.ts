import { test, expect } from "@playwright/test"
import { mockAuthAs, createUser, stabilizeHydration } from "../helpers"

/**
 * Checkout / Upgrade Cycle Tests
 *
 * Tests the subscription upgrade flow via mocked API:
 *   1. Authenticated user with an active monthly subscription
 *      (mock GET /api/v1/subscriptions/current)
 *   2. Click the upgrade/checkout CTA on the subscription page
 *   3. Mock POST /api/v1/subscriptions/checkout → { url, session_id, mock: true }
 *   4. Assert the demo-mode note renders (no real payment processed)
 *
 * Uses page.route API mocking.
 */

const MOCK_SUBSCRIPTION = {
  id: "sub_123",
  company_id: "company_1",
  billing_term: "monthly",
  status: "active",
  licensed_truck_count: 5,
  ai_copilot_enabled: false,
  priority_support_enabled: false,
  api_access_enabled: false,
  price_per_truck_erp_cents: 2900,
  price_per_truck_ai_cents: 2000,
  priority_support_price_cents: 4900,
  api_access_price_cents: 9900,
  annual_discount_pct: 10,
  current_period_end: "2026-09-01T00:00:00Z",
  service_credit_cents: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}

test.describe("Checkout / Upgrade Cycle", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
    // Authenticate as a regular user via the cookie-only refresh bootstrap.
    // NOTE: no localStorage seeding — the new provider removes legacy tokens
    // and bootstraps from the httpOnly refresh cookie (see e2e/helpers.ts).
    await mockAuthAs(page, createUser("user", { id: "2", email: "user@operionerp.xyz", name: "Regular User" }))

    // Current subscription → active monthly
    await page.route("**/api/v1/subscriptions/current", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_SUBSCRIPTION),
      })
    })
  })

  test("upgrade from an active monthly subscription shows demo-mode note", async ({ page }) => {
    // Mock the checkout POST → demo mode (no Stripe configured)
    let checkoutCalled = false
    await page.route("**/api/v1/subscriptions/checkout", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue()
        return
      }
      checkoutCalled = true
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          url: "https://checkout.stripe.com/demo-session",
          session_id: "cs_test_mock",
          mock: true,
        }),
      })
    })

    await page.goto("/dashboard/subscription")
    await expect(page).toHaveURL(/\/dashboard\/subscription/, { timeout: 15000 })

    // Subscription card renders with the active plan
    await expect(page.getByRole("heading", { name: /current plan/i })).toBeVisible()
    await expect(page.getByText(/active/i).first()).toBeVisible()

    // Click the upgrade/checkout CTA (role + text based, resilient to CTA rebuild)
    const upgradeCta = page
      .getByRole("button", { name: /upgrade|upgrade \/ pay|pay/i })
      .first()
    await expect(upgradeCta).toBeVisible()
    await upgradeCta.click()

    // The POST must have been made (poll — the route handler is async)
    await expect.poll(() => checkoutCalled, { timeout: 10000 }).toBe(true)

    // Demo-mode note renders (toast + trackEvent in the mock branch)
    await expect(page.getByText(/demo mode/i)).toBeVisible({ timeout: 10000 })
  })

  test("checkout CTA is present on the subscription page", async ({ page }) => {
    await page.goto("/dashboard/subscription")
    await expect(page).toHaveURL(/\/dashboard\/subscription/, { timeout: 15000 })
    await expect(page.getByRole("heading", { name: /current plan/i })).toBeVisible()

    // Verify at least one upgrade/pay CTA exists (presence check)
    const ctaCount = await page
      .getByRole("button", { name: /upgrade|pay/i })
      .count()
    expect(ctaCount).toBeGreaterThanOrEqual(1)
  })
})
