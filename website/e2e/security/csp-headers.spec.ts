import { test, expect } from "@playwright/test"
import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

/**
 * CSP / Security Headers
 *
 * The deployment target is Cloudflare Pages, which applies website/public/_headers
 * to every response. The e2e preview server (e2e/serve-preview.mjs) only emulates
 * static file serving + the SPA fallback — it deliberately does not inject the
 * production header set (it writes Content-Type/Cache-Control only), so the
 * source of truth for the deployed headers is `public/_headers` itself.
 *
 * These specs assert the committed header policy:
 *   1. Content-Security-Policy is defined and restrictive: script-src has no
 *      'unsafe-inline'/'unsafe-eval', object-src 'none', frame-ancestors 'none'.
 *   2. Baseline security headers are present (XFO DENY, nosniff, HSTS, COOP).
 *   3. Public pages still respond 200 through the e2e preview server.
 */

const WEBSITE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..")
const HEADERS_PATH = join(WEBSITE_ROOT, "public", "_headers")

test.describe("CSP / security headers", () => {
  test("Content-Security-Policy is deployed and restricts script execution", () => {
    const headers = readFileSync(HEADERS_PATH, "utf-8")
    const csp = headers.match(/Content-Security-Policy:\s*(.+)/)?.[1]
    expect(csp, "public/_headers must define Content-Security-Policy").toBeTruthy()

    expect(csp!).toContain("default-src 'self'")
    expect(csp!).toContain("object-src 'none'")
    expect(csp!).toContain("base-uri 'self'")
    expect(csp!).toContain("frame-ancestors 'none'")

    // script-src is the XSS-critical directive. style-src is allowed to keep
    // 'unsafe-inline' (Tailwind runtime injects styles) — that is a deliberate,
    // documented tradeoff and does not permit script execution.
    const scriptSrc = csp!.match(/script-src\s+([^;]+)/)?.[1] ?? ""
    expect(scriptSrc, "script-src must exist").toContain("'self'")
    expect(scriptSrc, "script-src must not allow inline script").not.toContain("'unsafe-inline'")
    expect(scriptSrc, "script-src must not allow eval").not.toContain("'unsafe-eval'")
  })

  test("baseline security headers are configured for deployment", () => {
    const headers = readFileSync(HEADERS_PATH, "utf-8")
    expect(headers).toContain("X-Frame-Options: DENY")
    expect(headers).toContain("X-Content-Type-Options: nosniff")
    expect(headers).toContain("Strict-Transport-Security:")
    expect(headers).toContain("Cross-Origin-Opener-Policy:")
    expect(headers).toContain("Referrer-Policy:")
  })

  test("public pages are served (HTTP 200) by the preview server", async ({ request }) => {
    for (const path of ["/", "/features", "/login", "/docs"]) {
      const res = await request.get(path)
      expect(res.status(), `${path} should return 200`).toBe(200)
    }
  })
})