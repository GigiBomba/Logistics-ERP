import { describe, it, expect } from "vitest"
import { getRouteLayout, DASHBOARD_ROUTE_PATHS } from "@/config/route-layouts"

describe("getRouteLayout", () => {
  it("maps dashboard routes to the dashboard layout", () => {
    expect(getRouteLayout("/dashboard")).toBe("dashboard")
    expect(getRouteLayout("/dashboard/devices")).toBe("dashboard")
    expect(getRouteLayout("/dashboard/subscription")).toBe("dashboard")
    expect(getRouteLayout("/dashboard/analytics")).toBe("dashboard")
  })

  it("maps parameterized dashboard routes via template matching", () => {
    expect(getRouteLayout("/dashboard/organizations/acme/settings")).toBe("dashboard")
  })

  it("maps public routes to the public layout", () => {
    expect(getRouteLayout("/")).toBe("public")
    expect(getRouteLayout("/features")).toBe("public")
    expect(getRouteLayout("/pricing")).toBe("public")
    expect(getRouteLayout("/blog/some-post")).toBe("public")
  })

  it("does not treat unknown dashboard-like paths as dashboard (explicit config only)", () => {
    // "/dashboard-v2" is not in the explicit config — falls back to public
    expect(getRouteLayout("/dashboard-v2")).toBe("public")
    // A hypothetical new dashboard route must be added to DASHBOARD_ROUTE_PATHS explicitly
    expect(getRouteLayout("/dashboard/some-future-route")).toBe("public")
  })

  it("covers every dashboard route declared in routes.tsx", () => {
    expect(DASHBOARD_ROUTE_PATHS).toEqual(
      expect.arrayContaining([
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
      ])
    )
  })
})
