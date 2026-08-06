import type { Page, Route } from "@playwright/test"

// ---------------------------------------------------------------------------
// Shared e2e helpers for the critical tier.
//
// The app's auth model (see src/contexts/auth-provider.tsx):
//   on mount the AuthProvider POSTs /api/v1/auth/refresh (no body — the backend
//   reads the refresh token from the httpOnly cookie) and then GETs
//   /api/v1/auth/me. Legacy localStorage access tokens are removed by the
//   provider. To authenticate in e2e we must mock BOTH endpoints — otherwise
//   the browser hits the real api.operionerp.xyz proxy and auth fails.
//
// NOTE: page.route() mocks must be registered BEFORE page.goto() so they are
// attached before the SSR'd page hydrates and fires its fetches. Registering
// in beforeEach is correct (routes persist across navigations).
// ---------------------------------------------------------------------------

export interface MockUser {
  id: string
  email: string
  name: string
  role: string
  email_verified: boolean
  created_at: string
  updated_at: string
  [key: string]: unknown
}

export function createUser(role: string, overrides: Partial<MockUser> = {}): MockUser {
  return {
    id: `${role}-1`,
    email: `${role}@operionerp.xyz`,
    name: `${role.charAt(0).toUpperCase() + role.slice(1)} User`,
    role,
    email_verified: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    ...overrides,
  }
}

const TOKEN_RESPONSE = {
  access_token: "mock-access-token",
  refresh_token: "mock-refresh-token",
  token_type: "bearer",
  expires_in: 3600,
}

/** Mock the app's cookie-only refresh bootstrap + /me profile fetch. */
export async function mockAuthAs(page: Page, user: MockUser): Promise<void> {
  await page.route("**/api/v1/auth/refresh", async (route: Route) => {
    if (route.request().method() !== "POST") {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(TOKEN_RESPONSE),
    })
  })
  await page.route("**/api/v1/auth/me", async (route: Route) => {
    if (route.request().method() !== "GET") {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user }),
    })
  })
}

/** Mock the login POST (optional MFA) + subsequent /me profile fetch. */
export async function mockLoginFlow(
  page: Page,
  user: MockUser,
  mfaRequired = false,
): Promise<void> {
  await page.route("**/api/v1/auth/token", async (route: Route) => {
    if (route.request().method() !== "POST") {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...TOKEN_RESPONSE,
        ...(mfaRequired
          ? { mfa_required: true, mfa_session_token: "mfa-session-token-123" }
          : {}),
      }),
    })
  })
  await page.route("**/api/v1/auth/me", async (route: Route) => {
    if (route.request().method() !== "GET") {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user }),
    })
  })
}

/** Seed localStorage on the real page origin (safe vs about:blank SecurityError). */
export function seedLocalStorage(page: Page, seed: () => void): void {
  page.addInitScript(seed)
}

/**
 * Pin the client to `navigator.onLine: false` to match the SSR environment.
 *
 * Node ≥21 exposes a global `navigator` whose `onLine` is `false`, so
 * OfflineDetector server-renders the "You are currently offline" banner. Real
 * browsers report `onLine: true`, which makes EVERY page hydration-mismatch
 * and regenerate the React tree — causing click/submit timing flakes in e2e.
 * Aligning the client makes the rendered trees match and the app deterministic.
 *
 * Call BEFORE the first page.goto() (e.g. in beforeEach).
 */
export function stabilizeHydration(page: Page): void {
  page.addInitScript(() => {
    Object.defineProperty(navigator, "onLine", { get: () => false, configurable: true })
    // Seed cookie consent so the consent dialog never renders and can't
    // intercept clicks/fills in specs. Key/version must match src/lib/consent.ts.
    localStorage.setItem(
      "operion_consent_v2",
      JSON.stringify({
        version: "2.0.0",
        timestamp: Date.now(),
        necessary: true,
        analytics: false,
        marketing: false,
      }),
    )
  })
}

/**
 * Wait until React has hydrated the page.
 *
 * `vike dev` compiles routes on demand, so on first load React attaches
 * several seconds AFTER the SSR HTML appears. Clicking submit before
 * hydration means the browser falls back to a native form GET (losing the
 * onSubmit handler). Poll for React's internal root marker AND for at least
 * one interactive element owned by React (`__reactProps$` on inputs/buttons/
 * links) — under parallel dev-server load the root marker can appear before
 * the route chunk's handlers are attached, so the element-level check is the
 * deterministic "interactive" signal. Then settle briefly.
 *
 * Call AFTER page.goto(), BEFORE fills/clicks.
 */
export async function waitForHydration(page: Page): Promise<void> {
  await page.waitForFunction(
    () => {
      const root = document.getElementById("root")
      const hasReactRoot =
        root !== null && Object.keys(root).some((k) => k.startsWith("__reactContainer"))
      if (!hasReactRoot) return false
      const interactive = document.querySelectorAll("input, button, select, textarea, a")
      return [...interactive].some((el) =>
        Object.keys(el).some((k) => k.startsWith("__reactProps")),
      )
    },
    { timeout: 30_000 },
  )
  await page.waitForTimeout(250)
}
