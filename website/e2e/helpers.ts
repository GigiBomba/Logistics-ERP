import { expect } from "@playwright/test"
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

/** Mock POST /api/v1/auth/logout → 200 so the provider's sign-out resolves. */
export async function mockLogout(page: Page): Promise<void> {
  await page.route("**/api/v1/auth/logout", async (route: Route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) })
  })
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
 * deterministic "interactive" signal.
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
  // Anti-flake buffer (100ms, reduced from 250ms): the element-level check
  // above gates on handler attachment, but redirect-driven specs
  // (protected-routes, chaos/offline) still showed hydration-timing flake with
  // zero settle time under parallel load. Keep this small buffer.
  await page.waitForTimeout(100)
}

// ---------------------------------------------------------------------------
// Consolidated auth setup
//
// The audit of the e2e suite found ~20 specs repeating the same auth bootstrap
// sequence: stabilizeHydration → mockAuthAs(→ mockLoginFlow/mockLogout) → goto,
// sometimes with a broad /api/v1/** data stub in front of the auth mocks. The
// helpers below parameterise exactly those variations.
//
// ORDERING (Playwright matches registered routes in REVERSE order of
// registration — the most recently registered matching handler wins):
//   stubData catch-all FIRST, then the auth mocks, so auth/refresh + auth/me
//   are answered by mockAuthAs and never fall through to the data stub.
// All registrations must happen BEFORE page.goto() (see the module header).
// ---------------------------------------------------------------------------

export interface AuthContextOptions {
  /** Mock user served by /api/v1/auth/me (build with createUser). */
  user: MockUser
  /** Also register mockLoginFlow (login POST + /me) — needed to submit the real login form. */
  login?: boolean
  /** Also register mockLogout — needed when the test signs out through the UI. */
  logout?: boolean
  /**
   * Register the broad `/api/v1/**` data stub (everything except
   * auth/refresh + auth/me → 200 `[]`). Registered BEFORE the auth mocks so
   * the auth routes still win (reverse-match order).
   */
  stubData?: boolean
  /** Call stabilizeHydration(page) first. Default true — pass false when the caller already did it. */
  stabilize?: boolean
}

/**
 * One-stop auth context: hydration stabilisation + the auth route mocks a
 * spec needs, in the canonical order, before the first page.goto().
 *
 * Returns the mock user that the context authenticates as (the resolved
 * `options.user`), so callers can reuse it in assertions.
 */
export async function setupAuthedContext(
  page: Page,
  options: AuthContextOptions,
): Promise<MockUser> {
  const { user } = options
  if (options.stabilize !== false) stabilizeHydration(page)
  if (options.stubData) {
    await page.route("**/api/v1/**", async (route: Route) => {
      const url = route.request().url()
      if (url.includes("/api/v1/auth/refresh") || url.includes("/api/v1/auth/me")) {
        await route.continue()
        return
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    })
  }
  await mockAuthAs(page, user)
  if (options.login) await mockLoginFlow(page, user)
  if (options.logout) await mockLogout(page)
  return user
}

/**
 * Wait for React hydration AND for the page's own form submit button to carry
 * React props before interacting with a submit button.
 *
 * `waitForHydration` can pass on shell elements (header/footer links) before
 * the lazily-loaded route chunk hydrates its form — clicking submit in that
 * window makes the browser fall back to a native form submission, so the zod
 * validation messages (or the mocked POST handlers) never fire. Gate on the
 * form's submit button itself.
 */
export async function waitForFormReady(page: Page): Promise<void> {
  await waitForHydration(page)
  // Gate on the FORM's own React props (onSubmit), not just the button's:
  // a button can carry React props one render before the form's submit handler
  // is attached, and clicking in that window makes the browser fall back to a
  // native form GET — e.g. /login?email=...&password=... (firefox MFA flake).
  await page.waitForFunction(
    () => {
      const form = document.querySelector("form")
      if (!form) return false
      const key = Object.keys(form).find((k) => k.startsWith("__reactProps"))
      const props = key ? (form as unknown as Record<string, { onSubmit?: unknown }>)[key] : null
      return !!props && typeof props.onSubmit === "function"
    },
    undefined,
    { timeout: 30_000 },
  )
  // Anti-flake buffer (same rationale as waitForHydration's 100ms): the
  // handler can attach one render before the controlled inputs are fully
  // hydrated; filling in that window lets a late render reset the RHF inputs,
  // so the submit runs empty and never navigates (observed: firefox
  // password-reset full-cycle login step under parallel load).
  await page.waitForTimeout(100)
}

export interface SubmitLoginFormOptions {
  email: string
  password: string
  /**
   * Assert this heading right after the readiness gate and BEFORE filling —
   * matches the specs that pin the login card copy before submitting.
   */
  heading?: string | RegExp
  /** URL expected after submitting. Default `/\/dashboard/`; pass null to skip. */
  expectUrl?: RegExp | null
  /**
   * Readiness gate before the first fill:
   *   "hydration" (default) — waitForHydration
   *   "form"                — waitForFormReady (stricter, for specs that
   *                            guard against the native-form-submit race)
   */
  gate?: "hydration" | "form"
  /** Timeout for the post-submit URL expectation. Default 15_000. */
  timeout?: number
}

/**
 * Submit the already-loaded login form: gate → optional heading assertion →
 * fill #email/#password → click the form's submit button → expect the redirect.
 *
 * Use this (instead of loginAs) when the page must NOT be re-navigated, e.g.
 * on `/login?returnUrl=…` where a goto would drop the query string.
 *
 * The submit button is the login form's single `button[type="submit"]`
 * ("Sign in") — the same element the specs previously targeted via
 * `getByRole("button", { name: /sign in/i })`.
 */
export async function submitLoginForm(
  page: Page,
  options: SubmitLoginFormOptions,
): Promise<void> {
  if (options.gate === "form") await waitForFormReady(page)
  else await waitForHydration(page)

  if (options.heading !== undefined) {
    await expect(page.getByRole("heading", { name: options.heading })).toBeVisible()
  }

  await page.fill("#email", options.email)
  await page.fill("#password", options.password)
  await page.click('button[type="submit"]')

  const expectUrl = options.expectUrl === undefined ? /\/dashboard/ : options.expectUrl
  if (expectUrl !== null) {
    await expect(page).toHaveURL(expectUrl, { timeout: options.timeout ?? 15_000 })
  }
}

export interface LoginAsOptions extends SubmitLoginFormOptions {
  /** Login route to navigate to first. Default "/login". */
  path?: string
}

/** Default password for the `loginAs(page, user)` form — the mocked API ignores it. */
export const DEFAULT_TEST_PASSWORD = "TestPass123!"

function isMockUser(value: MockUser | LoginAsOptions): value is MockUser {
  return "id" in value && "role" in value && "email" in value
}

/**
 * Drive the real login form end-to-end: goto the login route → readiness gate
 * → submit credentials → expect the post-login redirect.
 *
 * `userOrOptions` is either a MockUser (uses its email + DEFAULT_TEST_PASSWORD)
 * or the full option set (email/password/heading/expectUrl/gate/path).
 *
 * The auth route mocks must already be registered — pair with
 * `setupAuthedContext(page, { user, login: true })` before the first goto.
 */
export async function loginAs(
  page: Page,
  userOrOptions: MockUser | LoginAsOptions,
): Promise<void> {
  const options: LoginAsOptions = isMockUser(userOrOptions)
    ? { email: userOrOptions.email, password: DEFAULT_TEST_PASSWORD }
    : userOrOptions
  await page.goto(options.path ?? "/login")
  await submitLoginForm(page, options)
}
