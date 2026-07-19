import { test, expect } from "@playwright/test"

test.describe("Waitlist Flow", () => {
  test("waitlist page loads with signup form", async ({ page }) => {
    await page.goto("/waitlist")
    await expect(page).toHaveTitle(/Waitlist/)
    await expect(page.getByRole("heading", { name: /get on the list/i })).toBeVisible()
    await expect(page.getByLabelText(/company name/i)).toBeVisible()
    await expect(page.getByLabelText(/email/i)).toBeVisible()
    await expect(page.getByRole("button", { name: /join the waitlist/i })).toBeVisible()
  })

  test("waitlist page shows hero section", async ({ page }) => {
    await page.goto("/waitlist")
    await expect(page.getByRole("heading", { name: /waitlist/i }).first()).toBeVisible()
    await expect(page.getByText(/500\+/i)).toBeVisible()
    await expect(page.getByText(/professionals joined/i)).toBeVisible()
  })

  test("form shows validation errors for empty submit", async ({ page }) => {
    await page.goto("/waitlist")
    await page.getByRole("button", { name: /join the waitlist/i }).click()

    // Company name validation
    await expect(page.getByText(/company name must be at least/i)).toBeVisible()

    // Email validation
    await expect(page.getByText(/please enter a valid email/i)).toBeVisible()
  })

  test("form validates email format", async ({ page }) => {
    await page.goto("/waitlist")

    // Fill company name with valid value
    await page.getByLabelText(/company name/i).fill("Test Company")

    // Fill email with invalid value
    await page.getByLabelText(/email/i).fill("not-an-email")

    await page.getByRole("button", { name: /join the waitlist/i }).click()
    await expect(page.getByText(/please enter a valid email/i)).toBeVisible()
  })

  test("progressive disclosure toggle shows optional fields", async ({ page }) => {
    await page.goto("/waitlist")

    // Optional fields should not be visible initially
    await expect(page.getByLabelText(/contact name/i)).not.toBeVisible()

    // Click "More details" toggle
    await page.getByText(/more details/i).click()

    // Optional fields should now be visible
    await expect(page.getByLabelText(/contact name/i)).toBeVisible()
    await expect(page.getByLabelText(/company size/i)).toBeVisible()
    await expect(page.getByLabelText(/country/i)).toBeVisible()
    await expect(page.getByLabelText(/fleet size/i)).toBeVisible()
  })

  test("progressive disclosure toggle collapses optional fields", async ({ page }) => {
    await page.goto("/waitlist")

    // Expand
    await page.getByText(/more details/i).click()
    await expect(page.getByLabelText(/contact name/i)).toBeVisible()

    // Collapse
    await page.getByText(/less details/i).click()
    await expect(page.getByLabelText(/contact name/i)).not.toBeVisible()
  })

  test("benefits section is visible", async ({ page }) => {
    await page.goto("/waitlist")
    await expect(page.getByText(/early access/i).first()).toBeVisible()
    await expect(page.getByText(/priority access/i).first()).toBeVisible()
  })

  test("launch roadmap section is visible", async ({ page }) => {
    await page.goto("/waitlist")
    await expect(page.getByRole("heading", { name: /launch roadmap/i })).toBeVisible()
    await expect(page.getByText(/ai dispatch assistant/i)).toBeVisible()
    await expect(page.getByText(/mobile driver app/i)).toBeVisible()
  })
})
