import { test, expect } from "@playwright/test"
import { mockAuthAs, createUser, stabilizeHydration } from "../helpers"

/**
 * Support Ticket Cycle Tests
 *
 * Tests: submit bug report → appears in My Tickets → status visible.
 *
 * Uses mocked API data to be self-contained.
 */

const MOCK_TICKETS = [
  {
    id: 1,
    subject: "[Bug] Test Bug Report",
    status: "open",
    priority: "medium",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
]

test.describe("Support Ticket Cycle", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
    // Authenticate via the app's cookie-only refresh bootstrap (see e2e/helpers.ts).
    // The routes MUST be registered before page.goto so they intercept the
    // hydration fetches (vike SSR) instead of hitting the real API proxy.
    await mockAuthAs(page, createUser("user", { id: "2", email: "user@operionerp.xyz", name: "Regular User" }))
  })

  test("submit a bug report, see it in my tickets", async ({ page }) => {
    // Track whether the POST happened
    let ticketCreated = false

    await page.route("**/api/v1/support/tickets**", async (route) => {
      if (route.request().method() === "POST") {
        ticketCreated = true
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify(MOCK_TICKETS[0]),
        })
      } else if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(MOCK_TICKETS),
        })
      }
    })

    await page.goto("/dashboard/support")
    await expect(page).toHaveURL(/\/dashboard\/support/, { timeout: 15000 })
    // Exact match — the page also has an "ARGO Support" card heading
    await expect(page.getByRole("heading", { name: /^support$/i })).toBeVisible()

    // Fill in the bug report form (Submit Ticket tab is active by default)
    await page.fill("#bug-title", "Test Bug Report")
    await page.fill("#bug-desc", "This is a test bug description that is at least 20 characters long.")
    await page.fill("#bug-steps", "1. Go to X\n2. Click Y\n3. See error")

    // Click submit
    await page.getByRole("button", { name: /submit bug|report bug/i }).click()

    // Wait for the mutation to succeed
    await expect.poll(() => ticketCreated, { timeout: 10000 }).toBe(true)

    // Switch to "My Tickets" tab
    await page.getByRole("tab", { name: /my tickets/i }).click()

    // The ticket should appear in the list
    await expect(page.getByText("[Bug] Test Bug Report")).toBeVisible({ timeout: 10000 })

    // Status should be visible (open) — exact match: /open/i also hits the
    // status <option> "Open" in the bug-report form's priority select.
    await expect(page.getByText("open", { exact: true }).first()).toBeVisible()
  })

  test("my tickets tab shows empty state when no tickets exist", async ({ page }) => {
    await page.route("**/api/v1/support/tickets**", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
      }
    })

    await page.goto("/dashboard/support")
    await page.getByRole("tab", { name: /my tickets/i }).click()
    await expect(page.getByText(/no tickets/i)).toBeVisible()
  })
})
