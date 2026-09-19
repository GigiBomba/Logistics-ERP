import { test, expect } from "@playwright/test"
import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

/**
 * CSP / Security Headers
 *
 * Two layers:
 *   1. LIVE RESPONSES: e2e/serve-preview.mjs now applies the production header
 *      set from `public/_headers` (the same file Cloudflare Pages serves in
 *      production), so the preview server's response headers must carry the CSP
 *      + security headers end-to-end.
 *   2. DEPLOYMENT CONTRACT: `public/_headers` itself is asserted as the source
 *      of truth for what Cloudflare Pages will serve. The preview server reads
 *      that same file, so a mismatch would fail both layers.
 *
 * Note: `upgrade-insecure-requests` is part of the deployed _headers contract
 * but is deliberately not applied by the http-only preview server (it rewrites
 * subresource URLs to https on an http-served document, breaking asset
 * loading). The deployment-contract assertion below covers it.
 */

const WEBSITE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..")
const HEADERS_PATH = join(WEBSITE_ROOT, "public", "_headers")

const PUBLIC_PAGES = ["/", "/features", "/about", "/docs", "/login"]

/** Extract a single directive (e.g. script-src) from a CSP string. */
function cspDirective(csp: string, name: string): string {
  return csp.match(new RegExp(`${name}\\s+([^;]+)`))?.[1] ?? ""
}

/** Assert the shared restrictive-CSP invariants (script-src is the XSS gate). */
function assertRestrictiveCsp(csp: string) {
  expect(csp, "Content-Security-Policy must be defined").toBeTruthy()
  expect(csp).toContain("default-src 'self'")
  expect(csp).toContain("object-src 'none'")
  expect(csp).toContain("base-uri 'self'")
  expect(csp).toContain("frame-ancestors 'none'")

  // script-src is the XSS-critical directive. style-src is allowed to keep
  // 'unsafe-inline' (Tailwind runtime injects styles) — a deliberate, documented
  // tradeoff that does not permit script execution.
  const scriptSrc = cspDirective(csp, "script-src")
  expect(scriptSrc, "script-src must exist").toContain("'self'")
  expect(scriptSrc, "script-src must not allow inline script").not.toContain("'unsafe-inline'")
  expect(scriptSrc, "script-src must not allow eval").not.toContain("'unsafe-eval'")
}

test.describe("CSP / security headers", () => {
  test.describe("live response headers (preview server)", () => {
    for (const path of PUBLIC_PAGES) {
      test(`${path} serves Content-Security-Policy + security headers`, async ({ request }) => {
        const res = await request.get(path)
        expect(res.status(), `${path} should return 200`).toBe(200)

        const headers = res.headers()
        assertRestrictiveCsp(headers["content-security-policy"] ?? "")

        expect(headers["x-frame-options"]).toBe("DENY")
        expect(headers["x-content-type-options"]).toBe("nosniff")
        expect(headers["strict-transport-security"]).toBeTruthy()
        expect(headers["cross-origin-opener-policy"]).toBeTruthy()
        expect(headers["referrer-policy"]).toBeTruthy()
      })
    }
  })

  test.describe("deployment contract (public/_headers)", () => {
    test("Content-Security-Policy is defined and restricts script execution", () => {
      const headers = readFileSync(HEADERS_PATH, "utf-8")
      const csp = headers.match(/Content-Security-Policy:\s*(.+)/)?.[1]
      assertRestrictiveCsp(csp ?? "")

      // Production-only directive (https) — the http preview server intentionally
      // does not apply it (see e2e/serve-preview.mjs).
      expect(csp, "deployed CSP must upgrade insecure requests").toContain("upgrade-insecure-requests")
    })

    test("baseline security headers are configured for deployment", () => {
      const headers = readFileSync(HEADERS_PATH, "utf-8")
      expect(headers).toContain("X-Frame-Options: DENY")
      expect(headers).toContain("X-Content-Type-Options: nosniff")
      expect(headers).toContain("Strict-Transport-Security:")
      expect(headers).toContain("Cross-Origin-Opener-Policy:")
      expect(headers).toContain("Referrer-Policy:")
    })
  })
})