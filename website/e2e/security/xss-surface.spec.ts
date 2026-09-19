import { test, expect } from "@playwright/test"
import { readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

/**
 * XSS Surface Regression
 *
 * Pragmatic "script-injection vector" gate. Full DOM-XSS / content-sanitization
 * coverage belongs to the app lane (P4-2); what is assertable here cheaply and
 * deterministically:
 *
 *   1. No NEW dangerouslySetInnerHTML usage. The five audited usages render
 *      backend-controlled markdown/JSON through dedicated renderers and are
 *      reviewed on purpose. Any new sink forces a review — the gate flags new
 *      occurrences instead of silently allowing them.
 *   2. The deployed CSP does not allow inline/eval script execution
 *      (script-src without 'unsafe-inline'/'unsafe-eval'), so even injected
 *      markup cannot execute scripts in the deployed site.
 *   3. Served prerendered HTML of key public pages contains no raw inline event
 *      handler attributes (onerror=/onload=...) or javascript: URLs — the
 *      classic reflected/stored XSS payload carriers.
 */

const WEBSITE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..")
const SRC_ROOT = join(WEBSITE_ROOT, "src")

/** Files that intentionally use dangerouslySetInnerHTML (all audited). */
const AUDITED_HTML_SINKS = [
  "pages/docs/docs-article.tsx",
  "pages/admin/blog-editor.tsx",
  "pages/public/blog-article.tsx",
  "pages/public/tutorial-detail.tsx",
  "components/seo/structured-data.tsx",
]

function collectTsxFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    if (entry === "__tests__") continue
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) files.push(...collectTsxFiles(full))
    else if (entry.endsWith(".tsx")) files.push(full)
  }
  return files
}

test.describe("XSS surface regression", () => {
  test("no new dangerouslySetInnerHTML sinks beyond the audited set", () => {
    const sinks = collectTsxFiles(SRC_ROOT)
      .filter((file) => readFileSync(file, "utf-8").includes("dangerouslySetInnerHTML"))
      .map((file) => file.replaceAll("\\", "/").replace(/^.*?\bsrc\//, ""))
      .sort()

    expect(
      sinks,
      `dangerouslySetInnerHTML used in un-audited files:\n${sinks.join("\n")}`,
    ).toEqual([...AUDITED_HTML_SINKS].sort())
  })

  test("deployed CSP disallows inline/eval script execution", () => {
    const headers = readFileSync(join(WEBSITE_ROOT, "public", "_headers"), "utf-8")
    const csp = headers.match(/Content-Security-Policy:\s*(.+)/)?.[1] ?? ""
    const scriptSrc = csp.match(/script-src\s+([^;]+)/)?.[1] ?? ""
    expect(scriptSrc, "script-src must be defined").toBeTruthy()
    expect(scriptSrc, "script-src must not allow inline script").not.toContain("'unsafe-inline'")
    expect(scriptSrc, "script-src must not allow eval").not.toContain("'unsafe-eval'")
  })

  test("prerendered public pages contain no script-injection vectors", async ({ request }) => {
    // Lowercase on* attributes and javascript: URLs are how attacker-controlled
    // HTML executes script in the browser. React never emits event handlers as
    // HTML attributes, so any occurrence in served HTML is a real injection sink.
    const injectionPattern = /\son(?:error|load|click|mouseover|focus|blur)\s*=|href\s*=\s*["']javascript:/i
    const pages = ["/", "/features", "/pricing", "/about", "/contact", "/faq", "/blog", "/docs"]

    for (const path of pages) {
      const res = await request.get(path)
      expect(res.status(), `${path} should return 200`).toBe(200)
      const html = await res.text()
      const match = html.match(injectionPattern)
      expect(match, `${path} served HTML must not contain inline event handlers or javascript: URLs`).toBeNull()
    }
  })
})