import { test, expect, type Page } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "./helpers"

/**
 * Tab panels are client-state only (the custom Tabs returns null for inactive
 * panels), so the click must land after the ROUTE CHUNK hydrates the tablist —
 * `waitForHydration` alone can pass on shell header/footer elements while the
 * download chunk is still hydrating, and a click on the SSR'd tab button is a
 * no-op (observed: Legacy click left Stable selected). Gate on the tab itself.
 */
async function waitForTabsReady(page: Page): Promise<void> {
  await waitForHydration(page)
  await page.waitForFunction(
    () => {
      const tab = document.querySelector('[role="tab"]')
      return !!tab && Object.keys(tab).some((k) => k.startsWith("__reactProps"))
    },
    undefined,
    { timeout: 30_000 },
  )
}

test.describe("Download Flow", () => {
  test("download page loads with platform options", async ({ page }) => {
    await page.goto("/download")
    await expect(page).toHaveTitle(/Download/)
    await expect(page.getByRole("heading", { name: /operion desktop/i })).toBeVisible()
    await expect(page.getByText(/system requirements/i)).toBeVisible()
  })

  test("release channel tabs are present", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("tab", { name: /stable/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /beta/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /nightly/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /legacy/i })).toBeVisible()
  })

  test("stable tab is active by default", async ({ page }) => {
    await page.goto("/download")
    const stableTab = page.getByRole("tab", { name: /stable/i })
    await expect(stableTab).toHaveAttribute("data-state", "active")
  })

  // Tab panels are client-state only (custom Tabs returns null for inactive
  // panels), so the click must land after React attaches handlers — SSR buttons
  // are inert pre-hydration. stabilizeHydration also seeds cookie consent so
  // the fixed consent dialog can't intercept the tab click.
  test("beta tab switches content", async ({ page }) => {
    await stabilizeHydration(page)
    await page.goto("/download")
    await waitForTabsReady(page)
    await page.getByRole("tab", { name: /beta/i }).click()
    await expect(page.getByRole("heading", { name: /beta channel/i })).toBeVisible()
    await expect(page.getByRole("button", { name: /request access/i })).toBeVisible()
    await expect(page.getByPlaceholder(/search/i)).toBeVisible()
  })

  test("nightly tab shows warning", async ({ page }) => {
    await stabilizeHydration(page)
    await page.goto("/download")
    await waitForTabsReady(page)
    await page.getByRole("tab", { name: /nightly/i }).click()
    await expect(page.getByText(/not for production use/i)).toBeVisible()
  })

  test("legacy tab shows previous versions", async ({ page }) => {
    await stabilizeHydration(page)
    await page.goto("/download")
    await waitForTabsReady(page)
    await page.getByRole("tab", { name: /legacy/i }).click()
    await expect(page.getByText(/previous versions/i)).toBeVisible()
  })

  test("system requirements section displays hardware specs", async ({ page }) => {
    await page.goto("/download")
    // Scope to the system-requirements section: the primary download card also
    // says "Windows 10/11 (64-bit)", so a page-wide locator is a strict violation.
    const requirements = page.locator("section", {
      has: page.getByRole("heading", { name: /system requirements/i }),
    })
    await expect(requirements.getByText(/windows 10.*64-bit/i)).toBeVisible()
    await expect(requirements.getByText(/intel core i5/i)).toBeVisible()
    await expect(requirements.getByText(/8 gb minimum/i)).toBeVisible()
  })

  test("installation instructions are present", async ({ page }) => {
    await page.goto("/download")
    // exact:true — a plain string name still does substring matching, so
    // "Installation Instructions" also matched "Uninstallation Instructions".
    await expect(
      page.getByRole("heading", { name: "Installation Instructions", exact: true })
    ).toBeVisible()
    // Steps render as numbered circles + titles — there is no "Step N" copy.
    await expect(page.getByRole("heading", { name: /download the installer/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /run the installer/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /follow the setup wizard/i })).toBeVisible()
    await expect(page.getByRole("heading", { name: /launch operion erp/i })).toBeVisible()
  })

  test("toolkit download link has correct href", async ({ page }) => {
    await page.goto("/download")
    // Scroll to toolkit section
    await page.getByText(/toolkit/i).last().scrollIntoViewIfNeeded()

    const toolkitButtons = page.getByRole("link", { name: /download toolkit/i })
    await expect(toolkitButtons.first()).toBeVisible()
    await expect(toolkitButtons.first()).toHaveAttribute("href", /\/downloads\/operion-toolkit/)
  })

  test("documentation bundle button triggers alert", async ({ page }) => {
    await page.goto("/download")
    // Deviation: no "offline documentation" copy exists — the section heading
    // is "Documentation Bundle" (h3: "Operion Docs Offline").
    await page
      .getByRole("heading", { name: /documentation bundle/i })
      .scrollIntoViewIfNeeded()

    // The documentation bundle button should be visible
    await expect(page.getByRole("button", { name: /download docs bundle/i })).toBeVisible()
  })

  test("migration guides section is present", async ({ page }) => {
    await page.goto("/download")
    await expect(page.getByRole("heading", { name: /migration guides/i })).toBeVisible()
  })

  test("toolkit section links to documentation page", async ({ page }) => {
    await stabilizeHydration(page)
    await page.goto("/download")
    await waitForHydration(page)
    // Scope to the toolkit section: a page-wide /documentation/i .last() picked
    // the FOOTER "Documentation" link (/docs). The section's own link targets
    // /developers/toolkit — the expected destination was correct all along.
    const toolkitSection = page.locator("section", {
      has: page.getByRole("heading", { name: /operion developer toolkit/i }),
    })
    const docsLink = toolkitSection.getByRole("link", { name: /documentation/i })
    // Gate on the link itself: react-router <Link> needs hydrated handlers for
    // client-side nav (an SSR anchor would still navigate, but the section
    // scope must resolve before we assert the destination).
    await page.waitForFunction(
      () => {
        const link = document.querySelector('a[href="/developers/toolkit"]')
        return !!link && Object.keys(link).some((k) => k.startsWith("__reactProps"))
      },
      undefined,
      { timeout: 30_000 },
    )
    await docsLink.click()
    await expect(page).toHaveURL(/\/developers\/toolkit/)
  })
})
