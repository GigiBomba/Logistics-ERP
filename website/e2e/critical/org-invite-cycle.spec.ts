import { test, expect } from "@playwright/test"
import { mockAuthAs, createUser, stabilizeHydration, waitForHydration } from "../helpers"

/**
 * Organization Invite Cycle Tests
 *
 * Tests: invite teammate → appears in pending invitations.
 *         accept invitation in second browser context → success page.
 */

test.describe("Organization Invite Cycle", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
    // Authenticate as org admin via the cookie-only refresh bootstrap.
    await mockAuthAs(page, createUser("admin", { id: "1", email: "admin@operionerp.xyz", name: "Admin User" }))
  })

  test("invite a teammate and see pending invitation", async ({ page }) => {
    const orgSlug = "test-org"
    const inviteEmail = `teammate-${Date.now()}@operionerp.xyz`

    const inviteToken = "mock-invite-token-xyz"

    // Mock organizations list to return a valid org
    await page.route("**/api/v1/organizations**", async (route) => {
      const url = route.request().url()

      if (route.request().method() === "POST" && url.includes("/invitations")) {
        // Invitation creation response
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: 42,
            email: inviteEmail,
            role: "member",
            invited_by_name: "Admin User",
            status: "pending",
            token: inviteToken,
            created_at: new Date().toISOString(),
          }),
        })
      } else if (url.includes("/invitations") && route.request().method() === "GET") {
        // Pending invitations list
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: 42,
              email: inviteEmail,
              role: "member",
              invited_by_name: "Admin User",
              status: "pending",
              created_at: new Date().toISOString(),
            },
          ]),
        })
      } else if (url.includes("/members") && route.request().method() === "GET") {
        // Members list
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            { id: 1, name: "Admin User", email: "admin@operionerp.xyz", role: "admin", joined_at: "2026-01-01T00:00:00Z" },
          ]),
        })
      } else if (route.request().method() === "GET") {
        // GET /api/v1/organizations (list) and GET /api/v1/organizations/:slug (detail)
        if (url.endsWith("/organizations") || url.endsWith("/organizations/")) {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify([
              { id: "1", name: "Test Org", slug: orgSlug, user_role: "admin", member_count: 1, industry: "Logistics", subscription_tier: "Professional", created_at: "2026-01-01T00:00:00Z" },
            ]),
          })
        } else {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              id: "1", name: "Test Org", slug: orgSlug, user_role: "admin", member_count: 1, industry: "Logistics", subscription_tier: "Professional", created_at: "2026-01-01T00:00:00Z",
            }),
          })
        }
      }
    })

    // Navigate to organization settings
    await page.goto(`/dashboard/organizations/${orgSlug}/settings`)
    await expect(page).toHaveURL(new RegExp(`/dashboard/organizations/${orgSlug}/settings`), { timeout: 15000 })

    // Switch to Members tab
    await page.getByRole("tab", { name: /members/i }).click()

    // Fill invite form
    await page.fill("#invite-email", inviteEmail)

    // Select role (default is "member")
    await page.selectOption("#invite-role", "member")

    // Click Send Invitation
    await page.getByRole("button", { name: /send invitation/i }).click()

    // After success, the pending invitations section should appear with our invite
    await expect(page.getByText(inviteEmail)).toBeVisible({ timeout: 10000 })

    // The invitation should show "Pending" status badge
    await expect(page.getByText(/pending/i).first()).toBeVisible()
  })

  test("accept invitation in second browser context", async ({ browser }) => {
    const inviteToken = "mock-invite-token-xyz"
    const context = await browser.newContext()
    const page = await context.newPage()

    stabilizeHydration(page)

    // Mock the auth bootstrap (refresh + /me) in the new context BEFORE goto so
    // the accept page's AuthProvider never hits the dev-server proxy — removes
    // latent flake from unauthenticated network calls on page load.
    await mockAuthAs(
      page,
      createUser("member", { id: "99", email: "teammate@operionerp.xyz", name: "Teammate" }),
    )

    // Mock the accept invitation endpoint
    await page.route(
      `**/api/v1/organizations/invitations/${inviteToken}/accept`,
      async (route) => {
        if (route.request().method() === "POST") {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              id: 99,
              org_id: 1,
              user_id: "user-99",
              role: "member",
              status: "active",
              name: "Teammate",
              email: "teammate@operionerp.xyz",
              joined_at: new Date().toISOString(),
            }),
          })
        } else {
          await route.continue()
        }
      },
    )

    await page.goto(`/accept-invitation?token=${inviteToken}`)
    await waitForHydration(page)

    await expect(
      page.getByRole("heading", { name: /invitation accepted/i }),
    ).toBeVisible({ timeout: 10000 })
    await expect(
      page.getByRole("link", { name: /go to organizations/i }),
    ).toBeVisible()

    await context.close()
  })
})
