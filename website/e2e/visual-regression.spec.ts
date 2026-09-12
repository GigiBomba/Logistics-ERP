import { test, expect } from "@playwright/test"
import { mockAuthAs, createUser, stabilizeHydration } from "./helpers"

// Visual regression tests using Playwright's built-in screenshot comparison
// These test the key public pages across 3 viewports and 1 theme, plus the
// authenticated dashboard at desktop size.

const VIEWPORTS = [
  { width: 375, height: 812 },   // Mobile
  { width: 768, height: 1024 },  // Tablet
  { width: 1440, height: 900 },  // Desktop
]

// Both themes are rendered for every page. Light snapshot file names keep the
// existing baselines (`-chromium-win32.png`); dark appends `-dark` so the new
// baselines land in their own files without touching the light ones.
const THEMES = ["light", "dark"]

const PAGES = [
  { path: "/", name: "home" },
  { path: "/pricing", name: "pricing" },
  { path: "/waitlist", name: "waitlist" },
  { path: "/features", name: "features" },
  { path: "/blog", name: "blog" },
  { path: "/faq", name: "faq" },
  // /login is public and self-contained: the form renders from local state and
  // TurnstileWidget is a no-op without VITE_TURNSTILE_SITE_KEY, so no API
  // mocks are needed.
  { path: "/login", name: "login" },
]

// /blog is data-driven. Without mocks the article fetch races between the
// loading skeleton and the SPA-fallback error state (serve-preview answers
// /api/* with index.html, which is not JSON), so the screenshot was
// non-deterministic. Mock the API with fixed articles — same pattern as the
// navigation specs — so the baseline shows the real article cards.
const MOCK_BLOG_POSTS = [
  {
    id: 1,
    title: "Introducing AI-Powered OCR for Package Recognition",
    slug: "ai-powered-ocr-package-recognition",
    excerpt:
      "Our new AI-powered OCR engine can recognize package labels with 99.8% accuracy, even in challenging lighting conditions.",
    author_name: "Sarah Chen",
    category: "AI & Automation",
    tags: ["ai", "ocr", "product"],
    reading_time_minutes: 5,
    published_at: "2026-07-20T10:00:00Z",
  },
  {
    id: 2,
    title: "Trip Profitability: How to Calculate Profit Per Transport Job",
    slug: "how-to-calculate-trip-profitability-road-transport",
    excerpt:
      "Learn how to calculate trip profitability in road transport. This practical guide covers cost components, revenue tracking, and margin analysis for freight operators.",
    author_name: "Operion Team",
    category: "Profitability & Transport Finance",
    tags: ["trip-profitability", "transport-finance"],
    reading_time_minutes: 8,
    published_at: "2026-07-12T10:00:00Z",
  },
]

async function mockBlogApi(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/blog/posts**", async (route) => {
    const url = new URL(route.request().url())
    if (/\/blog\/posts\/[^/]+$/.test(url.pathname)) {
      // Force the frontend BLOG_ARTICLES fallback (deterministic article content).
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Post not found" }) })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: MOCK_BLOG_POSTS, total: MOCK_BLOG_POSTS.length, page: 1, page_size: 20 }),
    })
  })
  await page.route("**/api/v1/blog/authors/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "sarah-chen", name: "Sarah Chen", role: "Engineering Lead", bio: "Sarah leads engineering at Operion." }),
    })
  )
  await page.route("**/api/v1/blog/categories", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  )
}

/**
 * Freeze animations so screenshots are deterministic across runs:
 *  1. CSS: kill all CSS animations/transitions (handles animate-ping, hover states).
 *  2. WAAPI/CSS one-shots: finish() them to their end state; infinite ones pause().
 *  3. SMIL (SVG <animate>, e.g. the route-map truck on the home hero): freeze the
 *     SVG timeline at t=0 so the truck/line is at a fixed position every run.
 */
async function freezeAnimations(page: import("@playwright/test").Page) {
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation: none !important; transition: none !important; }",
  })
  await page.evaluate(() => {
    for (const anim of document.getAnimations()) {
      try {
        anim.finish()
      } catch {
        // Infinite/auto-rewind animations can't finish — pin them in place.
        anim.pause()
      }
    }
    for (const svg of Array.from(document.querySelectorAll("svg"))) {
      try {
        svg.pauseAnimations()
        svg.setCurrentTime(0)
      } catch {
        // Not an animated SVG — ignore.
      }
    }
  })
  // Make sure webfonts are loaded before painting (avoids FOUT diffs).
  await page.evaluate(() => document.fonts.ready)
}

test.describe("Visual Regression", () => {
  for (const page of PAGES) {
    for (const viewport of VIEWPORTS) {
      for (const theme of THEMES) {
        test(`${page.name} at ${viewport.width}x${viewport.height} (${theme})`, async ({ browser }) => {
          const context = await browser.newContext({
            viewport,
            colorScheme: theme,
          })
          // The Node SSR environment (Node ≥21) exposes a global `navigator`
          // whose `onLine` is `false`, so OfflineDetector server-renders the
          // offline banner. The real browser reports `onLine: true`, which makes
          // every page hydration-mismatch and regenerate the tree (flicker in
          // screenshots). Pin the client to `onLine: false` so the rendered
          // trees match and screenshots are deterministic.
          await context.addInitScript(() => {
            Object.defineProperty(navigator, "onLine", { get: () => false, configurable: true })
          })
          const pageObj = await context.newPage()
          // /blog is data-driven — mock the API (see mockBlogApi above) so the
          // screenshot shows the article cards deterministically instead of
          // racing between the loading skeleton and the error state.
          if (page.path === "/blog") {
            await mockBlogApi(pageObj)
          }
          await pageObj.goto(page.path, { waitUntil: "networkidle" })

          // Wait for the mocked articles to render BEFORE freezing fonts: the
          // cards are async, so fonts.ready would otherwise resolve before Inter
          // is used and the webfont swap would reflow the layout mid-screenshot.
          if (page.path === "/blog") {
            await expect(pageObj.getByRole("heading", { name: MOCK_BLOG_POSTS[0].title })).toBeVisible()
          }

          // /waitlist has a JS rAF-driven AnimatedCounter (setInterval ~16ms over
          // 1500ms) that CSS cannot stop. Scroll it into view and give it a fixed
          // 1800ms to settle at its target. MUST run before freezeAnimations:
          // the scroll triggers whileInView entrance animations, which freeze
          // then finishes — otherwise they drift mid-screenshot.
          if (page.path === "/waitlist") {
            const counter = pageObj.locator("span.font-semibold.text-white.tabular-nums").first()
            await counter.scrollIntoViewIfNeeded()
            await pageObj.waitForTimeout(1800)
          }

          // /login is client-rendered (not prerendered — see playwright.config.ts).
          // Wait for the form so the screenshot never catches the empty SPA shell
          // and freezeAnimations can settle the form's motion entrance.
          if (page.path === "/login") {
            await expect(pageObj.locator("#email")).toBeVisible()
          }

          await freezeAnimations(pageObj)

          const themeSuffix = theme === "dark" ? "-dark" : ""
          await expect(pageObj).toHaveScreenshot(`${page.name}-${viewport.width}x${viewport.height}${themeSuffix}.png`)
          await context.close()
        })
      }
    }
  }
})

test.describe("Dashboard visual regression", () => {
  for (const theme of THEMES) {
    test.describe(`dashboard theme ${theme}`, () => {
      test.use({ viewport: { width: 1440, height: 900 }, colorScheme: theme })

      test(`dashboard at 1440x900 (${theme})`, async ({ page }) => {
        stabilizeHydration(page)

        // Broad data-endpoint stub — exact pattern from
        // critical/public-navigation.spec.ts. Auth endpoints fall through to
        // mockAuthAs (registered AFTER this route, so it matches first) and every
        // other /api/v1/** call returns [].
        await page.route("**/api/v1/**", async (route) => {
          const url = route.request().url()
          if (url.includes("/api/v1/auth/refresh") || url.includes("/api/v1/auth/me")) {
            await route.continue()
            return
          }
          await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
        })
        await mockAuthAs(page, createUser("owner"))

        await page.goto("/dashboard", { waitUntil: "networkidle" })
        await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15000 })
        await expect(page.getByRole("heading", { name: /welcome back/i }).first()).toBeVisible()

        await freezeAnimations(page)

        const themeSuffix = theme === "dark" ? "-dark" : ""
        await expect(page).toHaveScreenshot(`dashboard-1440x900${themeSuffix}.png`)
      })
    })
  }
})
