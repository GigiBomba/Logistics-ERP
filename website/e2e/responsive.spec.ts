import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

test.describe("Responsive Design", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  test("mobile nav shows hamburger menu", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await waitForHydration(page)
    await expect(page.getByLabel(/toggle menu/i)).toBeVisible()
    // Menu is closed: the mobile-menu-only "Features" link (desktop shows it
    // under the "Product" dropdown) must not be visible. Scoped to the header
    // + exact name — the old unscoped locator strict-violated against the
    // hero "Explore Features" CTA and the footer "Features" link.
    await expect(page.getByRole("banner").getByRole("link", { name: "Features", exact: true })).not.toBeVisible()
  })

  test("mobile menu opens and shows all nav items", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await waitForHydration(page)
    await page.getByLabel(/toggle menu/i).click()
    // The header renders two <nav>s: the desktop nav (first) and the mobile
    // menu (the flex-col one). Scope the "all nav items" assertions to the
    // mobile menu — the old unscoped locators strict-violated against the
    // desktop nav / hero CTA / footer duplicates.
    const mobileMenu = page.getByRole("banner").locator('nav[class*="flex-col"]')
    for (const name of ["Home", "Features", "Pricing", "Download", "About", "Docs", "Contact"]) {
      await expect(mobileMenu.getByRole("link", { name, exact: true })).toBeVisible()
    }
  })

  test("mobile menu closes on nav item click", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await waitForHydration(page)
    await page.getByLabel(/toggle menu/i).click()
    // "Features" only exists as a standalone header link inside the open
    // mobile menu (desktop nav nests it under the "Product" dropdown), so the
    // banner-scoped exact locator is unambiguous.
    await page.getByRole("banner").getByRole("link", { name: "Features", exact: true }).click()
    await expect(page).toHaveURL(/\/features/)
  })

  test("desktop nav is fully visible", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await page.goto("/")
    await waitForHydration(page)
    // Desktop renders the full header nav. The mobile nav UI (hamburger +
    // mobile menu) is inactive: the mobile-menu-only "Features" link is absent
    // while the menu is closed. Note: the old `toggle menu not.toBeVisible()`
    // check is CSS-only (the button's `md:hidden` visibility) and cannot be
    // observed in the CSS-less e2e build, so the mobile-nav-inactive intent is
    // asserted via the mobile menu links instead. The desktop "Features" link
    // no longer exists top-level (redesign nested it under "Product"), so the
    // desktop-nav-visible intent is asserted via "Home" + "Pricing".
    await expect(page.getByRole("banner").getByRole("link", { name: "Home", exact: true })).toBeVisible()
    await expect(page.getByRole("banner").getByRole("link", { name: "Pricing", exact: true })).toBeVisible()
    await expect(page.getByRole("banner").getByRole("link", { name: "Features", exact: true })).not.toBeVisible()
  })

  test("footer stacks on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto("/")
    await waitForHydration(page)
    // Footer column headings via heading-role + exact name — the old
    // getByText("Product") strict-violated against 6 matches (footer h3, nav
    // links, "Product Tour" links, "Productization & Testing" h3, newsletter).
    const product = page.getByRole("heading", { name: "Product", exact: true })
    await product.scrollIntoViewIfNeeded()
    await expect(product).toBeVisible()
    await expect(page.getByRole("heading", { name: "Company", exact: true })).toBeVisible()
    await expect(page.getByRole("heading", { name: "Resources", exact: true })).toBeVisible()
  })
})
