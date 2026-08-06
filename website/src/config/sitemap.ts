// Shared sitemap configuration.
//
// Single source of truth for:
//   1. The static public routes vike pre-renders (pages/+onBeforePrerenderStart.ts)
//   2. The public/sitemap.xml generator (scripts/generate-sitemap.ts)
//
// Keep this free of runtime/environment imports (no import.meta.env) so the
// build script can run it under plain node/tsx.

export interface SitemapRoute {
  /** Path on the site, e.g. "/blog" (no trailing slash, no query). */
  path: string
  /** Sitemap priority hint (0.0 – 1.0). */
  priority: number
  /** Sitemap change frequency hint. */
  changefreq: string
  /** Optional ISO date override; when omitted the generator uses the build date. */
  lastmod?: string
}

const HIGH = 0.9
const MED = 0.7
const LOW = 0.5

export const sitemapRoutes: SitemapRoute[] = [
  // Core
  { path: "/", priority: 1.0, changefreq: "weekly" },
  { path: "/features", priority: HIGH, changefreq: "monthly" },
  { path: "/pricing", priority: HIGH, changefreq: "monthly" },
  { path: "/download", priority: HIGH, changefreq: "monthly" },
  { path: "/waitlist", priority: HIGH, changefreq: "weekly" },
  { path: "/about", priority: MED, changefreq: "monthly" },
  { path: "/mission", priority: LOW, changefreq: "monthly" },
  { path: "/contact", priority: MED, changefreq: "monthly" },
  { path: "/faq", priority: MED, changefreq: "monthly" },
  { path: "/argo", priority: LOW, changefreq: "monthly" },
  { path: "/changelog", priority: LOW, changefreq: "weekly" },
  { path: "/roadmap", priority: LOW, changefreq: "weekly" },
  { path: "/status", priority: LOW, changefreq: "weekly" },

  // Product & ecosystem
  { path: "/products", priority: MED, changefreq: "monthly" },
  { path: "/integrations", priority: LOW, changefreq: "monthly" },
  { path: "/integrators", priority: LOW, changefreq: "monthly" },
  { path: "/integrators-explorer", priority: LOW, changefreq: "monthly" },
  { path: "/enterprise", priority: MED, changefreq: "monthly" },
  { path: "/partners", priority: LOW, changefreq: "monthly" },
  { path: "/security", priority: LOW, changefreq: "monthly" },
  { path: "/trust", priority: LOW, changefreq: "monthly" },
  { path: "/trust-center", priority: LOW, changefreq: "monthly" },
  { path: "/route-demo", priority: MED, changefreq: "monthly" },
  { path: "/tools", priority: LOW, changefreq: "monthly" },
  { path: "/tutorials", priority: MED, changefreq: "weekly" },

  // Industries
  { path: "/industries/transport", priority: MED, changefreq: "monthly" },
  { path: "/industries/freight", priority: MED, changefreq: "monthly" },
  { path: "/industries/fleet", priority: MED, changefreq: "monthly" },
  { path: "/industries/owner-operators", priority: MED, changefreq: "monthly" },
  { path: "/industries/agriculture", priority: LOW, changefreq: "monthly" },
  { path: "/industries/construction", priority: LOW, changefreq: "monthly" },
  { path: "/industries/manufacturing", priority: LOW, changefreq: "monthly" },

  // Legal
  { path: "/privacy", priority: LOW, changefreq: "yearly" },
  { path: "/terms", priority: LOW, changefreq: "yearly" },
  { path: "/cookie-policy", priority: LOW, changefreq: "yearly" },
  { path: "/accessibility-statement", priority: LOW, changefreq: "yearly" },

  // Content hub (list pages get a fixed entry; article slugs are dynamic)
  { path: "/blog", priority: MED, changefreq: "weekly" },
]

/** Flat list of static public routes, consumed by the vike pre-render hook. */
export const publicRoutes: string[] = sitemapRoutes.map((r) => r.path)

export const SITE_BASE_URL = "https://operionerp.xyz"
