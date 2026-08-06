#!/usr/bin/env node
// Generates public/sitemap.xml from the shared route config (src/config/sitemap.ts)
// plus live blog slugs fetched from the public API at build time.
//
// Robust by design: if the API is unreachable during a build (CI without a
// backend), the sitemap is still emitted with the static route list only.
import { writeFileSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"
import { sitemapRoutes, SITE_BASE_URL } from "../src/config/sitemap"

const __dirname = dirname(fileURLToPath(import.meta.url))
const outFile = join(__dirname, "..", "public", "sitemap.xml")

const today = new Date().toISOString().slice(0, 10)

const BLOG_API_URL = "https://api.operionerp.xyz/api/v1/blog/posts"

// Optional build-time auth for the blog API. When set, an
// `Authorization: Bearer <token>` header is sent on the posts fetch so real
// slugs are retrieved instead of falling back to the static route list only.
function blogApiToken(): string | undefined {
  return process.env.BLOG_API_TOKEN || process.env.OPERION_BLOG_API_TOKEN || undefined
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

async function fetchBlogSlugs(): Promise<{ slug: string; lastmod: string }[]> {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 4000)
    const token = blogApiToken()
    const res = await fetch(BLOG_API_URL, {
      signal: controller.signal,
      ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}),
    })
    clearTimeout(timeout)
    if (!res.ok) return []
    const data: unknown = await res.json()
    const items = Array.isArray(data) ? data : (data as { items?: unknown[] }).items
    if (!Array.isArray(items)) return []
    return items
      .filter(
        (p): p is Record<string, unknown> =>
          typeof p === "object" && p !== null && typeof (p as Record<string, unknown>).slug === "string"
      )
      .map((p) => ({
        slug: String(p.slug),
        lastmod:
          typeof p.published_at === "string" && p.published_at ? p.published_at.slice(0, 10) : today,
      }))
  } catch {
    return []
  }
}

async function main(): Promise<void> {
  const blogSlugs = await fetchBlogSlugs()

  const lines: string[] = []
  lines.push('<?xml version="1.0" encoding="UTF-8"?>')
  lines.push('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

  for (const route of sitemapRoutes) {
    const lastmod = route.lastmod ?? today
    lines.push("  <url>")
    lines.push(`    <loc>${esc(`${SITE_BASE_URL}${route.path}`)}</loc>`)
    lines.push(`    <lastmod>${lastmod}</lastmod>`)
    lines.push(`    <changefreq>${route.changefreq}</changefreq>`)
    lines.push(`    <priority>${route.priority.toFixed(1)}</priority>`)
    lines.push("  </url>")
  }

  for (const post of blogSlugs) {
    lines.push("  <url>")
    lines.push(`    <loc>${esc(`${SITE_BASE_URL}/blog/${post.slug}`)}</loc>`)
    lines.push(`    <lastmod>${post.lastmod}</lastmod>`)
    lines.push("    <changefreq>monthly</changefreq>")
    lines.push("    <priority>0.6</priority>")
    lines.push("  </url>")
  }

  lines.push("</urlset>")
  writeFileSync(outFile, lines.join("\n") + "\n", "utf8")
  console.log(
    `Sitemap written: ${outFile} (${sitemapRoutes.length} static routes + ${blogSlugs.length} blog posts)`
  )
}

main().catch((err) => {
  console.error("Failed to generate sitemap:", err)
  process.exit(1)
})
