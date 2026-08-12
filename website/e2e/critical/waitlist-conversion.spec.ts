import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "../helpers"

test.describe("Waitlist Conversion", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  test("land on home, click waitlist CTA, submit, see referral code", async ({ page }) => {
    const testEmail = `waitlist-${Date.now()}@test.com`

    // Mock the waitlist API so the flow is deterministic offline:
    //   - GET /api/v1/waitlist/count → live counter value
    //   - POST /api/v1/waitlist/join → referral code (success view)
    await page.route("**/api/v1/waitlist/count", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 513, cached_at: "2026-08-02T00:00:00Z" }),
      })
    })
    await page.route("**/api/v1/waitlist/join", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue()
        return
      }
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({ status: "joined", referral_code: "REF-TEST123" }),
      })
    })

    // ─── Home page ─────────────────────────────────────────────
    await page.goto("/")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /The Complete Logistics Operating System/i })).toBeVisible()

    // Click the primary CTA which links to /waitlist
    await page.getByRole("link", { name: /see the ai in action|early access|waitlist/i }).first().click()
    await expect(page).toHaveURL(/\/waitlist/)

    // ─── Waitlist form ─────────────────────────────────────────
    // The SPA transition renders the SSR'd form immediately; under parallel
    // load React may still be hydrating when we interact, and a late
    // client-side render can reset the RHF inputs. Give the client a beat to
    // take over the form before filling.
    await page.waitForTimeout(1000)
    await expect(page.locator("#company_name")).toBeVisible()
    await expect(page.locator("#email")).toBeVisible()

    // Fill in the waitlist form
    await page.fill("#company_name", "Waitlist Test Corp")
    await page.fill("#email", testEmail)

    // Submit the form. Use the accessible button name — the app-shell footer
    // also renders a newsletter form with a type="submit" button (labelled
    // "Subscribe"), so the bare CSS selector is ambiguous.
    await page.getByRole("button", { name: /join waitlist/i }).click()

    // ─── Success state ─────────────────────────────────────────
    // After successful submission, the page shows the joined confirmation
    // and the referral code section ("Your referral code" + monospace code).
    await expect(page.getByText("Your referral code")).toBeVisible({ timeout: 15000 })

    // A referral code should be displayed (monospace span)
    const referralCodeLocator = page.locator(".font-mono")
    await expect(referralCodeLocator.first()).toBeVisible()
    await expect(referralCodeLocator.first()).toHaveText("REF-TEST123")
  })
})
