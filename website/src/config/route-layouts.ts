/**
 * Explicit route → layout assignment.
 *
 * Replaces the old `pathname.startsWith("/dashboard")` heuristic that lived
 * inside AppShell with an explicit, single-source-of-truth config. Every route
 * that should render inside the dashboard shell must be listed here; anything
 * not listed falls back to the "public" shell. Add new dashboard routes here
 * as well as in routes.tsx.
 */
export type AppLayout = "dashboard" | "public"

export const DASHBOARD_ROUTE_PATHS: readonly string[] = [
  "/dashboard",
  "/dashboard/profile",
  "/dashboard/company",
  "/dashboard/subscription",
  "/dashboard/downloads",
  "/dashboard/docs",
  "/dashboard/support",
  "/dashboard/settings",
  "/dashboard/organizations",
  "/dashboard/organizations/:slug/settings",
  "/dashboard/licenses",
  "/dashboard/devices",
  "/dashboard/onboarding",
  "/dashboard/billing",
  "/dashboard/referrals",
  "/dashboard/activity",
  "/dashboard/analytics",
]

/**
 * Matches a route template containing `:param` segments (e.g.
 * "/dashboard/organizations/:slug/settings") against an actual pathname.
 */
function matchesParamTemplate(template: string, pathname: string): boolean {
  if (!template.includes(":")) return false
  const templateSegments = template.split("/")
  const pathSegments = pathname.split("/")
  if (templateSegments.length !== pathSegments.length) return false
  return templateSegments.every((segment, i) => segment.startsWith(":") || segment === pathSegments[i])
}

/** Resolves the shell layout for a given pathname from the explicit config. */
export function getRouteLayout(pathname: string): AppLayout {
  if (pathname === "/dashboard" || DASHBOARD_ROUTE_PATHS.includes(pathname)) {
    return "dashboard"
  }
  if (DASHBOARD_ROUTE_PATHS.some((path) => matchesParamTemplate(path, pathname))) {
    return "dashboard"
  }
  return "public"
}
