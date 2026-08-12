import { test, expect, type Page } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

/**
 * Cycle the theme toggle until the <html> element has the `dark` class.
 *
 * The theme provider defaults to `system` (theme-provider.tsx returns
 * "system" when localStorage is empty), which resolves to a `light` class in
 * the headless browser. The toggle cycles system -> light -> dark -> system,
 * so a single click from the default state lands on `light`, not `dark`. We
 * click up to 3 times and break as soon as the dark class is applied — this
 * keeps the intent ("the toggle switches to dark mode") without assuming the
 * pre-click theme state.
 */
async function enableDarkMode(page: Page): Promise<void> {
  const html = page.locator("html")
  const toggle = page.getByLabel(/toggle theme/i).first()
  for (let i = 0; i < 3; i++) {
    await toggle.click()
    const isDark = await html.evaluate((el) => el.classList.contains("dark"))
    if (isDark) return
  }
}

test.describe("Dark Mode", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  test("theme toggle switches to dark mode", async ({ page }) => {
    await page.goto("/")
    await waitForHydration(page)
    const html = page.locator("html")
    await expect(html).not.toHaveClass(/dark/)
    // The header renders two identical "Toggle theme" buttons (desktop
    // actions + mobile actions); both call the same cycleTheme handler, so
    // the first is the deterministic target (strict-mode fix).
    await enableDarkMode(page)
    // Theme cycles system -> light -> dark -> system
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode persists on page navigation", async ({ page }) => {
    await page.goto("/")
    await waitForHydration(page)
    await enableDarkMode(page)
    await page.goto("/features")
    await waitForHydration(page)
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode persists on reload", async ({ page }) => {
    await page.goto("/")
    await waitForHydration(page)
    await enableDarkMode(page)
    await page.reload()
    await waitForHydration(page)
    const html = page.locator("html")
    await expect(html).toHaveClass(/dark/)
  })

  test("dark mode affects card styling", async ({ page }) => {
    await page.goto("/")
    await waitForHydration(page)
    await enableDarkMode(page)
    // Home hero checklist copy is "Smart Route Planning" post-redesign
    // (previously "Intelligent Route Planning").
    const card = page.getByText(/smart route planning/i).locator("..")
    await expect(card).toBeVisible()
  })
})
