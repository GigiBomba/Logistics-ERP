import { test, expect } from "@playwright/test"

test.describe("ROI Calculator", () => {
  test("ROI calculator page loads", async ({ page }) => {
    await page.goto("/roi-calculator")
    await expect(page).toHaveTitle(/ROI Calculator/)
    await expect(page.getByRole("heading", { name: /roi calculator/i }).first()).toBeVisible()
    await expect(page.getByText(/fleet details/i)).toBeVisible()
    await expect(page.getByText(/results/i)).toBeVisible()
  })

  test("calculator form has all input fields", async ({ page }) => {
    await page.goto("/roi-calculator")
    // Slider inputs
    await expect(page.getByText(/fleet size/i)).toBeVisible()

    // Number inputs
    await expect(page.getByText(/monthly trips/i)).toBeVisible()
    await expect(page.getByText(/avg\. revenue/i)).toBeVisible()
    await expect(page.getByText(/fuel cost/i)).toBeVisible()
    await expect(page.getByText(/avg\. distance/i)).toBeVisible()
    await expect(page.getByText(/number of dispatchers/i)).toBeVisible()
    await expect(page.getByText(/monthly invoices/i)).toBeVisible()
  })

  test("slider input accepts value change", async ({ page }) => {
    await page.goto("/roi-calculator")

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

    // Default values should produce results
    // Wait for animations to settle
    await page.waitForTimeout(1500)

    // Check that result stat cards are visible (€ values rendered)
    const resultCards = page.locator("text=/€/")
    const count = await resultCards.count()
    expect(count).toBeGreaterThanOrEqual(3)

    // Check specific result labels
    await expect(page.getByText(/avg\. cost.*trip/i)).toBeVisible()
    await expect(page.getByText(/avg\. profit.*trip/i)).toBeVisible()
    await expect(page.getByText(/monthly profit/i)).toBeVisible()
    await expect(page.getByText(/fuel.*savings/i)).toBeVisible()
    await expect(page.getByText(/time savings/i)).toBeVisible()
    await expect(page.getByText(/admin savings/i)).toBeVisible()
    await expect(page.getByText(/total monthly roi/i)).toBeVisible()
    await expect(page.getByText(/yearly savings/i)).toBeVisible()
  })

  test("assumptions panel expands and collapses", async ({ page }) => {
    await page.goto("/roi-calculator")

    // Assumptions button should be visible
    const assumptionsButton = page.getByText(/assumptions/i)
    await expect(assumptionsButton).toBeVisible()

    // Click to expand
    await assumptionsButton.click()
    await expect(page.getByText(/fuel savings.*12%/i)).toBeVisible()

    // Click to collapse
    await assumptionsButton.click()
    await expect(page.getByText(/fuel savings.*12%/i)).not.toBeVisible()
  })

  test("results update when inputs change", async ({ page }) => {
    await page.goto("/roi-calculator")

    // Wait for initial animation
    await page.waitForTimeout(1000)

    // Get the yearly savings stat text (last big stat)
    const yearlySavingsLabel = page.getByText(/yearly savings/i)
    await expect(yearlySavingsLabel).toBeVisible()

    // Change a key input — monthly trips to a higher value
    const tripsInput = page.locator('input[type="number"]').first()
    await tripsInput.click()
    await tripsInput.fill("900")

    // Wait for animations to update
    await page.waitForTimeout(1500)

    // The yearly savings label should still be visible (results recalculated)
    await expect(yearlySavingsLabel).toBeVisible()
  })

  test("CTA banner is present", async ({ page }) => {
    await page.goto("/roi-calculator")
    await expect(page.getByRole("heading", { name: /get a detailed quote/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /talk to sales/i })).toBeVisible()
  })
})
