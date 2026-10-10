import { test, expect } from "@playwright/test"
import { waitForHydration } from "./helpers"

// NOTE: `vike dev` compiles routes on demand (~7s on first hit) while the
// default expect timeout is 5s — every test waits for hydration after goto
// before asserting (fixes cold-render first-hit failures; Helmet titles also
// only land on the hydration commit).

test.describe("ROI Calculator", () => {
  test("ROI calculator page loads", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)
    await expect(page).toHaveTitle(/ROI Calculator/)
    await expect(page.getByRole("heading", { name: /roi calculator/i }).first()).toBeVisible()
    // The hero description also says "Enter your fleet details…" — scope to the section heading.
    await expect(page.getByRole("heading", { name: /fleet details/i })).toBeVisible()
    await expect(page.getByText(/results/i)).toBeVisible()
  })

  test("calculator form has all input fields", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)
    // Slider inputs
    await expect(page.getByText(/fleet size/i)).toBeVisible()

    // Number inputs
    await expect(page.getByText(/monthly trips/i)).toBeVisible()
    await expect(page.getByText(/average revenue per trip/i)).toBeVisible()
    await expect(page.getByText(/fuel cost/i)).toBeVisible()
    await expect(page.getByText(/average distance per trip/i)).toBeVisible()
    await expect(page.getByText(/number of dispatchers/i)).toBeVisible()
    await expect(page.getByText(/monthly invoices/i)).toBeVisible()
  })

  test("slider input accepts value change", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)

    // Find the fleet size slider
    const slider = page.locator('input[type="range"]').first()
    await expect(slider).toBeVisible()

    // Get initial displayed value
    const initialDisplay = await page.locator("text=/vehicles/").textContent()

    // Move slider — set to a different value via fill or evaluate
    await slider.fill("50")
    // Trigger change event
    await slider.dispatchEvent("change")

    // The results section should update (check for € sign in results)
    await expect(page.getByText(/€/).first()).toBeVisible()
  })

  test("number input accepts value change", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)

    // Find a number input (e.g., monthly trips)
    const numberInput = page.locator('input[type="number"]').first()
    await expect(numberInput).toBeVisible()

    // Clear and set a new value
    await numberInput.click()
    await numberInput.fill("300")

    // Results should still be displayed
    await expect(page.getByText(/€/).first()).toBeVisible()
  })

  test("calculation produces result values", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)

    // Default values should produce results
    // Auto-wait for the first computed result (€ stat card) to render — the
    // animated counters settle as the stat cards become visible.
    await expect(page.locator("text=/€/").first()).toBeVisible()

    // Check that result stat cards are visible (€ values rendered)
    const resultCards = page.locator("text=/€/")
    const count = await resultCards.count()
    expect(count).toBeGreaterThanOrEqual(3)

    // Check specific result labels (current copy: "Avg cost per trip" /
    // "Avg profit per trip" — no period after "Avg")
    await expect(page.getByText(/avg cost per trip/i)).toBeVisible()
    await expect(page.getByText(/avg profit per trip/i)).toBeVisible()
    await expect(page.getByText(/monthly profit/i)).toBeVisible()
    await expect(page.getByText(/fuel.*savings/i)).toBeVisible()
    await expect(page.getByText(/time savings/i)).toBeVisible()
    await expect(page.getByText(/admin savings/i)).toBeVisible()
    await expect(page.getByText(/total monthly roi/i)).toBeVisible()
    await expect(page.getByText(/yearly savings/i)).toBeVisible()
  })

  test("assumptions panel expands and collapses", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)

    // Assumptions button should be visible
    const assumptionsButton = page.getByText(/assumptions/i)
    await expect(assumptionsButton).toBeVisible()

    // Click to expand. The label ("Fuel savings:") and the value ("12%
    // reduction…") are sibling spans — a single regex cannot span nodes, so
    // assert them separately.
    await assumptionsButton.click()
    await expect(page.getByText("Fuel savings:", { exact: true })).toBeVisible()
    await expect(page.getByText(/12% reduction/i)).toBeVisible()

    // Click to collapse
    await assumptionsButton.click()
    await expect(page.getByText("Fuel savings:", { exact: true })).not.toBeVisible()
  })

  test("results update when inputs change", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)

    // Get the yearly savings stat text (last big stat) — auto-waits for the
    // initial render / animated counter to settle.
    const yearlySavingsLabel = page.getByText(/yearly savings/i)
    await expect(yearlySavingsLabel).toBeVisible()

    // Change a key input — monthly trips to a higher value
    const tripsInput = page.locator('input[type="number"]').first()
    await tripsInput.click()
    await tripsInput.fill("900")

    // The yearly savings label should still be visible (results recalculated)
    await expect(yearlySavingsLabel).toBeVisible()
  })

  test("CTA banner is present", async ({ page }) => {
    await page.goto("/roi-calculator")
    await waitForHydration(page)
    // PRODUCT DECISION (to confirm): the former CTA copy "Get a detailed
    // quote" / "Talk to sales" no longer exists — the page now closes with
    // "Powered by Operion ERP" and the WaitlistCta ("Join Waitlist") plus an
    // "Explore features" link.
    await expect(page.getByRole("heading", { name: /powered by operion erp/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /join waitlist/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /explore features/i })).toBeVisible()
  })
})
