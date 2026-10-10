import { test, expect } from "@playwright/test"
import { waitForHydration } from "./helpers"

// vike dev compiles routes on demand (~7s first hit) while the default expect
// timeout is 5s — every test waits for hydration after goto (and before any
// click: the progressive-disclosure toggle and submit button are React
// handlers that don't exist until the route chunk hydrates).
//
// NOTE: `page.getByLabelText` does not exist in Playwright (it throws
// "not a function") — these specs use `page.getByLabel`. All waitlist fields
// have proper <label htmlFor>/<id> associations, so getByLabel resolves them.

test.describe("Waitlist Flow", () => {
  test("waitlist page loads with signup form", async ({ page }) => {
    await page.goto("/waitlist")
    await waitForHydration(page)
    await expect(page).toHaveTitle(/Waitlist/)
    await expect(page.getByRole("heading", { name: /dispatch taking all night/i })).toBeVisible()
    await expect(page.getByLabel(/company name/i)).toBeVisible()
    await expect(page.getByLabel(/email/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /join waitlist/i })).toBeVisible()
  })

  test("waitlist page shows hero section", async ({ page }) => {
    // Mock the count endpoint BEFORE goto so the hydration-time fetch is
    // intercepted (the live API is unreachable from the e2e sandbox and would
    // leave the skeleton rendered instead of the "N+" figure).
    await page.route("**/api/v1/waitlist/count", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 500, cached_at: new Date().toISOString() }),
      })
    )
    await page.goto("/waitlist")
    await waitForHydration(page)
    await expect(page.getByRole("heading", { name: /dispatch taking all night/i })).toBeVisible()
    // The counter animates from 0 only once it scrolls into view (motion
    // useInView) and it sits below the fold at 1280×720 — scroll it into the
    // viewport, then wait for the animated figure.
    const joinedText = page.getByText(/logistics professionals have joined/i)
    await joinedText.scrollIntoViewIfNeeded()
    await expect(page.getByText(/500\+/i)).toBeVisible()
    await expect(joinedText).toBeVisible()
  })

  test("form shows validation errors for empty submit", async ({ page }) => {
    await page.goto("/waitlist")
    await waitForHydration(page)
    await page.getByRole("button", { name: /join waitlist/i }).click()

    // Company name validation
    await expect(page.getByText(/company name must be at least/i)).toBeVisible()

    // Email validation
    await expect(page.getByText(/please enter a valid email/i)).toBeVisible()
  })

  test("form validates email format", async ({ page }) => {
    await page.goto("/waitlist")
    await waitForHydration(page)

    // Fill company name with valid value
    await page.getByLabel(/company name/i).fill("Test Company")

    // Fill email with invalid value
    const emailField = page.getByLabel(/email/i)
    await emailField.fill("not-an-email")

    await page.getByRole("button", { name: /join waitlist/i }).click()
    // The email input is type="email", so the browser's native format
    // validation blocks submission BEFORE the React/zod handler runs — the zod
    // message "Please enter a valid email" never renders for a malformed
    // (non-empty) value (it does render for an empty field, covered by the
    // empty-submit test). Assert the field is still invalid and the form did
    // not navigate.
    await expect(emailField).toHaveJSProperty("validity.valid", false)
    await expect(page).toHaveURL(/\/waitlist/)
  })

  test("progressive disclosure toggle shows optional fields", async ({ page }) => {
    await page.goto("/waitlist")
    await waitForHydration(page)

    // Optional fields should not be visible initially
    await expect(page.getByLabel(/contact name/i)).not.toBeVisible()

    // Click the progressive-disclosure toggle — the label flips with state
    // ("More details (optional)" collapsed → "Less details" expanded), so the
    // locator must match either wording to stay valid after the click.
    const toggle = page.getByRole("button", { name: /more details|less details/i })
    await expect(toggle).toHaveAttribute("aria-expanded", "false")
    await toggle.click()
    await expect(toggle).toHaveAttribute("aria-expanded", "true")
    await expect(toggle).toHaveText(/less details/i)

    // Optional fields should now be visible
    await expect(page.getByLabel(/contact name/i)).toBeVisible()
    await expect(page.getByLabel(/company size/i)).toBeVisible()
    await expect(page.getByLabel(/country/i)).toBeVisible()
    await expect(page.getByLabel(/fleet size/i)).toBeVisible()
  })

  test("progressive disclosure toggle collapses optional fields", async ({ page }) => {
    await page.goto("/waitlist")
    await waitForHydration(page)
    // The label flips with expansion state: "More details (optional)" when
    // collapsed → "Less details" when expanded — match either wording so the
    // locator resolves in both states.
    const toggle = page.getByRole("button", { name: /more details|less details/i })

    // Collapsed initially: label reads "More details (optional)"
    await expect(toggle).toHaveText(/more details/i)

    // Expand — label flips to "Less details"
    await toggle.click()
    await expect(toggle).toHaveAttribute("aria-expanded", "true")
    await expect(toggle).toHaveText(/less details/i)
    await expect(page.getByLabel(/contact name/i)).toBeVisible()

    // Collapse — label flips back to "More details (optional)" while
    // aria-expanded returns to false.
    await toggle.click()
    await expect(toggle).toHaveAttribute("aria-expanded", "false")
    await expect(toggle).toHaveText(/more details/i)
    await expect(page.getByLabel(/contact name/i)).not.toBeVisible()
  })

  test("benefits section is visible", async ({ page }) => {
    await page.goto("/waitlist")
    await waitForHydration(page)
    await expect(page.getByText(/early access/i).first()).toBeVisible()
    // PRODUCT DECISION (to confirm): the "Priority Access"/"Priority Support"
    // benefit is not part of the current benefits grid (waitlist.tsx) — the
    // six benefits are Early Access, AI Copilot Access, Workflow Automation,
    // Launch Notifications, Extended Free Trial, Reduced Subscription Price.
    // Assert an existing benefit instead.
    await expect(page.getByText(/ai copilot access/i).first()).toBeVisible()
  })

  test("waitlist page shows benefits grid (launch roadmap section removed)", async ({ page }) => {
    await page.goto("/waitlist")
    await waitForHydration(page)
    // PRODUCT DECISION (prominent): the former "Launch roadmap" section
    // (heading "Launch roadmap", milestones "AI dispatch assistant" /
    // "mobile driver app") no longer exists on /waitlist — the page now ends
    // with the benefits grid. Assert the current content instead.
    await expect(page.getByRole("heading", { name: /what you'll get/i })).toBeVisible()
    await expect(page.getByText(/workflow automation/i).first()).toBeVisible()
    await expect(page.getByText(/launch notifications/i).first()).toBeVisible()
  })
})
