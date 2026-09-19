import { test, expect, type Page } from "@playwright/test"
import { mockAuthAs, mockLoginFlow, createUser, stabilizeHydration, waitForHydration, type MockUser } from "../helpers"

/**
 * Token Storage Security
 *
 * The app's auth model (see src/contexts/auth-provider.tsx + src/api/client.ts):
 *   - the access token lives in MEMORY only (React state / module variable),
 *   - the refresh token is an httpOnly cookie set by the backend — never
 *     persisted to web storage,
 *   - legacy localStorage/sessionStorage token keys (`operion-access-token`,
 *     `operion-refresh-token`) are scrubbed on every auth transition.
 *
 * These specs assert:
 *   1. Anonymous visitors expose no token material in web storage.
 *   2. After a real login flow the access token is never serialized into
 *      localStorage/sessionStorage and the legacy keys are scrubbed.
 */

const LEGACY_TOKEN_KEYS = ["operion-access-token", "operion-refresh-token"] as const

test.describe("Token storage security", () => {
  test.beforeEach(async ({ page }) => {
    stabilizeHydration(page)
  })

  /** Dump both web storages as plain objects for assertion. */
  function readStorage(page: Page) {
    return page.evaluate(() => {
      const read = (store: Storage): Record<string, string> => {
        const out: Record<string, string> = {}
        for (let i = 0; i < store.length; i++) {
          const key = store.key(i)
          if (key !== null) out[key] = store.getItem(key) ?? ""
        }
        return out
      }
      return { localStorage: read(localStorage), sessionStorage: read(sessionStorage) }
    })
  }

  test("anonymous pages expose no token keys in web storage", async ({ page }) => {
    await page.goto("/login")
    await waitForHydration(page)

    const storage = await readStorage(page)
    const allKeys = [...Object.keys(storage.localStorage), ...Object.keys(storage.sessionStorage)]
    for (const key of LEGACY_TOKEN_KEYS) {
      expect(allKeys, `${key} must not exist in web storage on anonymous pages`).not.toContain(key)
    }
  })

  test("after login the access token stays in memory — never persisted to storage", async ({ page }) => {
    const email = `sec-token-${Date.now()}@operion.dev`
    const password = "TestPass123!"
    const user: MockUser = createUser("user", { id: "sec-token-1", email, name: "Security Tester" })

    // Seed the legacy localStorage keys BEFORE the app loads so the login flow
    // is forced to scrub them (the AuthProvider removes them on every auth
    // transition). sessionStorage is not seeded: the modern app never writes
    // token material there — the legacy sessionStorage key is only scrubbed in
    // the refresh-failure/logout paths, and its absence is asserted below.
    await page.addInitScript(() => {
      localStorage.setItem("operion-access-token", "legacy-access-token")
      localStorage.setItem("operion-refresh-token", "legacy-refresh-token")
    })

    // Session-wide auth mocks, registered BEFORE any goto so they intercept the
    // hydration fetches (same pattern as critical/auth-full-cycle.spec.ts).
    await mockAuthAs(page, user)
    await mockLoginFlow(page, user)

    await page.goto("/login")
    await waitForHydration(page)
    await page.fill("#email", email)
    await page.fill("#password", password)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 })

    const storage = await readStorage(page)
    const allStorage = JSON.stringify({ ...storage.localStorage, ...storage.sessionStorage })

    // Legacy token keys must be scrubbed by the login flow.
    for (const key of LEGACY_TOKEN_KEYS) {
      expect(Object.keys(storage.localStorage), `localStorage must not contain ${key}`).not.toContain(key)
      expect(Object.keys(storage.sessionStorage), `sessionStorage must not contain ${key}`).not.toContain(key)
    }
    // sessionStorage must not carry any other token-shaped key either.
    const sessionKeys = Object.keys(storage.sessionStorage)
    expect(sessionKeys.filter((k) => /token/i.test(k)), "sessionStorage must not contain token keys").toEqual([])

    // The mocked login returns access_token "mock-access-token" (e2e/helpers.ts).
    // It is held in memory by the app — it must never appear in web storage.
    expect(allStorage, "the access token value must not be serialized into web storage").not.toContain(
      "mock-access-token",
    )
  })
})