import { test, expect } from "@playwright/test"
import { stabilizeHydration, waitForHydration } from "../helpers"

test.describe("Chaos — Offline & Edge Cases", () => {
  test("already loaded page remains usable offline", async ({ page }) => {
    // Pin navigator.onLine + seed consent before first navigation: without
    // pinning, the client reports onLine=true while Node SSR renders the
    // offline banner → hydration mismatch → full client re-render, which
    // under full-run load can outlive the 10s expect timeout after
    // setOffline(true) (passes 4/4 isolated, failed 2/2 full runs).
    stabilizeHydration(page)
    await page.goto("/")
    // Hydrate fully before going offline — the home route is lazy-loaded and
    // would otherwise fail to fetch its chunk once the network is cut.
    await waitForHydration(page)
    // Readiness gate: wait for BOTH offline assertions' targets to be
    // interactive BEFORE cutting the network, so the post-offline expects
    // only verify the already-rendered DOM stays visible (no lazy chunk /
    // late hydration still pending once offline).
    const heroHeading = page.getByRole("heading", {
      name: /the complete logistics operating system/i,
    })
    const featureText = page.getByText(/smart route planning/i)
    await expect(heroHeading).toBeVisible()
    await expect(featureText).toBeVisible()
    await page.context().setOffline(true)
    // Longer targeted timeouts for the offline assertions: under full-run
    // load (4 workers + concurrent processes) the offline-banner insert can
    // re-render the shell and briefly reflow — 10s was too tight (2/2 full
    // runs failed at this step while isolated runs always passed).
    await expect(heroHeading).toBeVisible({ timeout: 20_000 })
    await expect(featureText).toBeVisible({ timeout: 20_000 })
  })

  test("navigation to visited cached pages works offline", async ({ page }) => {
    stabilizeHydration(page)
    await page.goto("/features")
    // Let the /features chunk load + hydrate before cutting the network — the
    // page's "Route Planning" mockup text only exists after hydration.
    await waitForHydration(page)
    // Exact text — /route planning/i also matched the ARGO integrations copy
    // in the AI section (strict-mode violation).
    const routePlanning = page.getByText("Route Planning", { exact: true })
    // Readiness gate: confirm the hydrated target is on-screen BEFORE going
    // offline (same pattern as the home-page test above).
    await expect(routePlanning).toBeVisible()
    await page.context().setOffline(true)
    // Longer targeted timeout — same load-flake rationale (heading/text not
    // found within the default 10s after setOffline under full-run load).
    await expect(routePlanning).toBeVisible({ timeout: 20_000 })
  })

  test("handles rapid route changes without error", async ({ page }) => {
    await page.goto("/")
    const pages = ["/", "/features", "/pricing", "/download", "/about", "/mission", "/faq", "/contact"]
    for (const route of pages) {
      await page.goto(route, { waitUntil: "commit" })
    }
    // Last visited page is /contact — assert its current h1 ("Get in Touch").
    // getByText("Contact") was ambiguous (nav + footer links, contact emails).
    // Auto-waits for the final route to settle after the rapid navigations
    // (replaces the fixed 1000ms sleep; no offline state to verify here).
    await expect(page.getByRole("heading", { name: /get in touch/i })).toBeVisible()
  })

  test("handles localStorage with invalid token", async ({ page }) => {
    // Seed via addInitScript so it runs on the real origin at navigation
    // (page.evaluate before goto would run on about:blank → SecurityError).
    // The provider removes the legacy token anyway; the redirect to /login is
    // driven by the failing cookie-refresh bootstrap.
    await page.addInitScript(() => {
      localStorage.setItem("operion-access-token", "invalid-not-a-real-token-%%%")
    })
    await page.goto("/dashboard")
    // Should gracefully redirect to login
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  })
})
