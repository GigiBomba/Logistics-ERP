import { test, expect } from "@playwright/test"
import type { Page } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

/**
 * Scope to the Pricing FAQ SectionWrapper: `button[aria-expanded]` page-wide
 * resolves first to the header language-switcher (aria-haspopup="listbox"),
 * not the accordion. The FAQ section is the <section> whose heading is
 * "Pricing FAQ"; it contains exactly the 4 accordion toggles.
 */
function faqSection(page: Page) {
  return page.locator("section", {
    has: page.getByRole("heading", { name: /pricing faq/i }),
  })
}

function faqButtons(page: Page) {
  return faqSection(page).locator("button[aria-expanded]")
}

/**
 * Gate on the FAQ toggle itself: `waitForHydration` can pass on shell header
 * buttons (e.g. the language switcher) before the pricing route chunk hydrates
 * the accordion — clicking the SSR'd toggle would then be a no-op.
 */
async function waitForFaqReady(page: Page): Promise<void> {
  await waitForHydration(page)
  await page.waitForFunction(
    () => {
      const heading = [...document.querySelectorAll("h2")].find((h) =>
        /pricing faq/i.test(h.textContent ?? ""),
      )
      const btn = heading
        ?.closest("section")
        ?.querySelector("button[aria-expanded]")
      return !!btn && Object.keys(btn).some((k) => k.startsWith("__reactProps"))
    },
    undefined,
    { timeout: 30_000 },
  )
}

test.describe("Pricing Flow", () => {
  test("pricing page loads with heading and coming soon card", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page).toHaveTitle(/Pricing/)
    await expect(page.getByRole("heading", { name: /simple, transparent pricing/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /coming soon/i })).toBeVisible()
    // Current coming-soon card copy (pricing.devMessage) — the old "currently
    // in active development" phrasing only survives in other locales.
    await expect(
      page.getByText(/autonomous dispatch engine is operational and free during the current phase/i)
    ).toBeVisible()
    await expect(page.getByRole("link", { name: /sign up for early access/i })).toBeVisible()
  })

  test("early access button links to register", async ({ page }) => {
    await page.goto("/pricing")
    await page.getByRole("link", { name: /sign up for early access/i }).click()
    await expect(page).toHaveURL(/\/register/)
  })

  test("pricing FAQ section is visible", async ({ page }) => {
    await page.goto("/pricing")
    await expect(page.getByRole("heading", { name: /pricing faq/i })).toBeVisible()
  })

  test("FAQ accordion expands on click", async ({ page }) => {
    await stabilizeHydration(page)
    await page.goto("/pricing")
    await waitForFaqReady(page)

    // There should be multiple FAQ items (buttons with aria-expanded)
    const buttons = faqButtons(page)
    const count = await buttons.count()
    expect(count).toBeGreaterThanOrEqual(4)

    // First FAQ item should be collapsed initially
    await expect(buttons.nth(0)).toHaveAttribute("aria-expanded", "false")

    // Click to expand the first FAQ item
    await buttons.nth(0).click()
    await expect(buttons.nth(0)).toHaveAttribute("aria-expanded", "true")

    // The answer content should now be visible (scoped to the FAQ section so
    // the page header's similar dispatch-engine copy can't satisfy it).
    await expect(
      faqSection(page).getByText(/autonomous dispatch engine is operational and free to use/i)
    ).toBeVisible()
  })

  test("FAQ accordion collapses when clicked again", async ({ page }) => {
    await stabilizeHydration(page)
    await page.goto("/pricing")
    await waitForFaqReady(page)

    const buttons = faqButtons(page)
    await buttons.nth(0).click()
    await expect(buttons.nth(0)).toHaveAttribute("aria-expanded", "true")

    // Click again to collapse
    await buttons.nth(0).click()
    await expect(buttons.nth(0)).toHaveAttribute("aria-expanded", "false")
  })

  test("FAQ accordion items toggle independently", async ({ page }) => {
    await stabilizeHydration(page)
    await page.goto("/pricing")
    await waitForFaqReady(page)

    const buttons = faqButtons(page)

    // Expand first item
    await buttons.nth(0).click()
    await expect(buttons.nth(0)).toHaveAttribute("aria-expanded", "true")

    // Expand second item — first should collapse (single open)
    await buttons.nth(1).click()
    await expect(buttons.nth(1)).toHaveAttribute("aria-expanded", "true")
  })

  test("CTA section is visible at bottom of page", async ({ page }) => {
    await page.goto("/pricing")
    // Current CTA title (pricing.ctaTitle) — no "Get Early Access" heading.
    const ctaSection = page.locator("section", {
      has: page.getByRole("heading", { name: /start using autonomous dispatching/i }),
    })
    await expect(
      page.getByRole("heading", { name: /start using autonomous dispatching/i })
    ).toBeVisible()
    await expect(ctaSection.getByRole("link", { name: /get started/i })).toBeVisible()
  })
})
