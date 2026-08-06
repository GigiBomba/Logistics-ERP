import { test, expect, type Page } from "@playwright/test"
import type { UserRole } from "../../src/types"
import { mockAuthAs, createUser, stabilizeHydration, type MockUser } from "../helpers"

/**
 * RBAC Boundary Tests
 *
 * The app enforces RBAC at the route level (see src/components/auth):
 *   - /dashboard/* routes only require authentication (ProtectedRoute).
 *   - /admin/* routes require owner|admin (AdminLayout → RequireRole); other
 *     roles are redirected to /dashboard.
 *   - unauthenticated users are redirected to /login?returnUrl.
 *
 * The dashboard sidebar nav renders all items regardless of role, so nav-link
 * visibility is NOT the RBAC boundary anymore — route access is. These tests
 * assert the route-level guard behaviour via mocked auth state.
 */

test.describe("RBAC Boundaries", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  async function gotoAdminOps(page: Page, user: MockUser) {
    await mockAuthAs(page, user)
    // Ops data endpoints — return empty lists so the page renders for allowed roles
    await page.route("**/api/v1/ops**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
    // NOTE: `/admin/ops` renders the OpsTickets index route (there is no
    // `/admin/ops/tickets` path — it falls through to the 404 catch-all).
    await page.goto("/admin/ops")
  }

  const privilegedRoles: UserRole[] = ["owner", "admin"]
  const restrictedRoles: UserRole[] = ["manager", "dispatcher", "driver"]

  for (const role of privilegedRoles) {
    test(`${role} can access /admin/ops`, async ({ page }) => {
      await gotoAdminOps(page, createUser(role))

      // Allowed — stays on the admin ops console (no redirect to /dashboard)
      await expect(page).toHaveURL(/\/admin\/ops/, { timeout: 15000 })
      await expect(page.getByRole("heading", { name: /ops console/i })).toBeVisible()
    })
  }

  for (const role of restrictedRoles) {
    test(`${role} is redirected to /dashboard from /admin/ops`, async ({ page }) => {
      await gotoAdminOps(page, createUser(role))

      // Denied — redirected to /dashboard (RequireRole default fallback)
      await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15000 })
    })
  }

  test("unauthenticated user is redirected to login from /dashboard", async ({ page }) => {
    // No auth mocks → refresh fails → user is null → ProtectedRoute redirects
    await page.goto("/dashboard")
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  })
})
