import { defineConfig, devices } from "@playwright/test"

/**
 * Playwright configuration for Operion website E2E tests.
 * Tests are served via the Vite dev server.
 */
export default defineConfig({
  testDir: "./",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  // Local runs get 1 retry (CI keeps 2): the vike dev server compiles routes on
  // demand and the parallel cross-browser suites still show rare load-induced
  // interaction flakes even after the deterministic hydration / cold-route
  // gates were fixed (2026-10-07). Retried tests are reported as "flaky",
  // never silently passed; deterministic failures fail every attempt.
  retries: process.env.CI ? 2 : 1,
  // Local workers capped (was "half the cores"): the vike dev server compiles
  // routes on demand and high parallelism causes load-induced flake
  // (cold-route timeouts, hydration races).
  workers: process.env.CI ? 2 : 4,
  reporter: [["list"], ["html", { open: "never" }]],
  expect: {
    // Extra headroom for cold-route renders under parallel load. Raised from
    // 10s to 20s (2026-10-07): SPA link clicks trigger on-demand vike-dev route
    // compiles; during loaded 2-worker cross-browser runs the first compile can
    // exceed 10s and the URL assertion failed despite the link working
    // (firefox v3-navigation / download-flow / auth-flow flakes).
    timeout: 20_000,
    toHaveScreenshot: {
      // AA rasterization-noise tolerance for the visual suite: allow at most
      // 50 differing pixels per comparison. Chromium's anti-aliased text/glyph
      // rendering flickers by a handful of pixels between runs (observed:
      // features dark 2px, faq dark 2px, dashboard light 4px). 50px is ~0.004%
      // of a 1440x900 shot — far below any layout change (a single shifted
      // text line is thousands of pixels), so it absorbs sub-pixel AA jitter
      // without masking copy, layout, or color regressions.
      maxDiffPixels: 50,
    },
  },
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
  webServer: {
    command: "npx vite",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    cwd: "..",
  },
})
