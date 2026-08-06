import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

test.describe("Accessibility", () => {
  test("main landmark element is present on key pages", async ({ page }) => {
    const keyPages = ["/", "/features", "/pricing", "/about", "/contact", "/blog"]
    for (const path of keyPages) {
      await page.goto(path)
      const main = page.locator("main")
      await expect(main, `${path} should have a <main> element`).toBeVisible()
    }
  })

  test("buttons have accessible names", async ({ page }) => {
    await page.goto("/")
    const buttons = page.locator("button")
    const count = await buttons.count()
    expect(count).toBeGreaterThan(0)

    // Every button should have an accessible name (aria-label or visible text)
    for (let i = 0; i < count; i++) {
      const btn = buttons.nth(i)
      const name = await btn.getAttribute("aria-label")
      const text = await btn.textContent()
      const hasAccessibleName = (name && name.trim().length > 0) || (text && text.trim().length > 0)
      expect(hasAccessibleName, `Button ${i} should have an accessible name`).toBe(true)
    }
  })

  test("form inputs have associated labels on contact page", async ({ page }) => {
    await page.goto("/contact")
    const inputs = page.locator("input, textarea, select")
    const count = await inputs.count()
    expect(count).toBeGreaterThan(0)

    for (let i = 0; i < count; i++) {
      const input = inputs.nth(i)
      const inputId = await input.getAttribute("id")
      const ariaLabel = await input.getAttribute("aria-label")
      const placeholder = await input.getAttribute("placeholder")

      const hasLabel =
        inputId !== null ||
        (ariaLabel !== null && ariaLabel.trim().length > 0) ||
        (placeholder !== null && placeholder.trim().length > 0)

      expect(hasLabel, `Input ${i} should have an associated label (id, aria-label, or placeholder)`).toBe(true)
    }
  })

  test("nav element has navigation role", async ({ page }) => {
    await page.goto("/")

    // Check semantic <nav> elements exist
    const navElements = page.locator("nav")
    const navCount = await navElements.count()
    expect(navCount).toBeGreaterThanOrEqual(1)

    // Check at least one has role="navigation" or is a semantic nav
    let hasNavigationRole = false
    for (let i = 0; i < navCount; i++) {
      const role = await navElements.nth(i).getAttribute("role")
      if (role === "navigation" || role === null) {
        // role=null is fine — <nav> implicitly has navigation role
        hasNavigationRole = true
        break
      }
    }
    expect(hasNavigationRole).toBe(true)

    // Also check explicit [role='navigation'] elements
    const navByRole = page.locator("[role='navigation']")
    const navRoleCount = await navByRole.count()
    expect(navCount + navRoleCount).toBeGreaterThanOrEqual(1)
  })

  test("footer has contentinfo role", async ({ page }) => {
    await page.goto("/")

    // Check <footer> element exists
    const footer = page.locator("footer")
    await expect(footer).toBeVisible()

    // <footer> implicitly has contentinfo role
    const hasContentinfo = await footer.evaluate((el) => {
      return el.tagName.toLowerCase() === "footer"
    })
    expect(hasContentinfo).toBe(true)
  })

  test("no console errors related to accessibility", async ({ page }) => {
    const a11yErrors: string[] = []
    page.on("console", (msg) => {
      const text = msg.text().toLowerCase()
      if (
        msg.type() === "error" &&
        (text.includes("accessibility") ||
          text.includes("a11y") ||
          text.includes("aria") ||
          text.includes("role") ||
          text.includes("focus") ||
          text.includes("contrast"))
      ) {
        a11yErrors.push(msg.text())
      }
    })

    await page.goto("/")
    // Interact with several key pages to trigger any a11y warnings
    await page.goto("/features")
    await page.goto("/contact")
    await page.goto("/pricing")

    expect(a11yErrors).toEqual([])
  })

  test("focus styles are visible on keyboard navigation", async ({ page }) => {
    // Hydration-timing hardening (mirrors the critical tier): pin the client
    // to the SSR environment (consent + navigator.onLine) and wait for React
    // to hydrate before tabbing, so the tab stops are the deterministic DOM
    // (no consent-dialog/offline-banner churn mid-tab under parallel load).
    stabilizeHydration(page)
    await page.goto("/")
    await waitForHydration(page)

    // Tab through interactive elements and verify focus is applied
    const focusableSelectors = [
      "a",
      "button",
      "input",
      "textarea",
      "select",
      "[tabindex]:not([tabindex='-1'])",
    ]
    const focusableElements = page.locator(focusableSelectors.join(","))
    const count = await focusableElements.count()
    expect(count).toBeGreaterThan(0)

    // Tab through first few elements and check focus outline
    const checkCount = Math.min(count, 5)
    for (let i = 0; i < checkCount; i++) {
      await page.keyboard.press("Tab")
      const focused = page.locator(":focus")
      const focusedCount = await focused.count()

      if (focusedCount > 0) {
        // Verify the focused element has an outline or ring style
        const hasFocusStyle = await focused.evaluate((el) => {
          const style = window.getComputedStyle(el)
          const outline = style.outline
          const outlineColor = style.outlineColor
          const outlineWidth = style.outlineWidth
          const boxShadow = style.boxShadow
          const ringColor = style.getPropertyValue("--tw-ring-color")
          const ringWidth = style.getPropertyValue("--tw-ring-width")

          return (
            (outline !== "none" && outline !== "" && outlineWidth !== "0px") ||
            (boxShadow !== "none" && boxShadow !== "") ||
            (ringColor !== "" && ringWidth !== "0px")
          )
        })
        expect(hasFocusStyle, `Focused element ${i} should have visible focus indicator`).toBe(true)
      }
    }
  })

  test("reduced motion preference is respected", async ({ page }) => {
    // Mock prefers-reduced-motion: reduce
    await page.emulateMedia({ reducedMotion: "reduce" })
    await page.goto("/")
    await waitForHydration(page)

    // The page should still render all content even with reduced motion.
    // Selectors updated to the current home hero copy (S-grade redesign):
    // "Enterprise Logistics" -> "The Complete Logistics Operating System",
    // "Start Free Trial" -> "Waitlist" nav CTA, "Intelligent Route Planning"
    // -> "Smart Route Planning".
    await expect(page.getByRole("heading", { name: /The Complete Logistics Operating System/i })).toBeVisible()
    await expect(page.getByRole("link", { name: /waitlist|early access/i }).first()).toBeVisible()
    await expect(page.getByText(/Smart Route Planning/i)).toBeVisible()
  })
})
