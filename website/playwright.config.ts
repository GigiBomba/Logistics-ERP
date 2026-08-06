import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  webServer: {
    // Production build + preview: `vike dev` compiles routes on demand, which
    // makes hydration slow (~7s) and flakes under parallel workers. A static
    // build+preview is deterministic across workers. `vite preview` must run
    // on :3000 (see preview.port in vite.config.ts) to match baseURL.
    //
    // NOTE: serves dist/client via e2e/serve-preview.mjs (SPA fallback) instead
    // of `vite preview` — vite preview 404s every non-prerendered route
    // (/login, /dashboard/*, ...) because it doesn't honour the app's
    // Cloudflare `_redirects` SPA fallback. serve-preview.mjs replicates that
    // fallback. The `tsc -b` gate of `npm run build` is skipped (vike build
    // doesn't typecheck) — `npm run typecheck` is validated separately.
    // globals.css is imported from pages/+Page.tsx so vike emits + links the
    // CSS in the prerendered pages (styled e2e, same as production).
    command: "npx vike build && node e2e/serve-preview.mjs",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 300_000, // vike build takes a while
  },
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  expect: {
    timeout: 15_000,
    toHaveScreenshot: {
      maxDiffPixels: 100,  // ~0.1% of a 1440x900 screen
      threshold: 0.2,      // 0.2% color difference per pixel
    },
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
})
