import { Outlet, useLocation } from "react-router"
import { AppNavigate } from "@/components/navigation/app-navigate"
import { envConfig } from "@/config/env"

/**
 * MaintenanceGuard — layout route that checks `VITE_MAINTENANCE_MODE`.
 *
 * When the flag is active, all public routes nested under this guard are
 * redirected to `/maintenance`, except:
 *  - Error pages (/500, /maintenance, /offline)
 *  - Dashboard routes (/dashboard/*)
 *  - Auth routes (/login, /register, /forgot-password, etc.)
 *
 * Usage (in App.tsx):
 *   <Route element={<MaintenanceGuard />}>
 *     … public routes …
 *   </Route>
 */
export default function MaintenanceGuard() {
  const { pathname } = useLocation()

  // Feature flag off → render children as normal
  if (!envConfig.maintenanceMode) {
    return <Outlet />
  }

  // Never redirect: error pages, maintenance page itself, dashboard, auth
  const publicErrorPattern = /^\/(500|maintenance|offline)($|\/)/
  const dashboardPattern = /^\/dashboard($|\/)/
  const authPattern = /^\/(login|register|forgot-password|reset-password|verify-email|accept-invitation|auth\/)($|\/)/

  if (
    publicErrorPattern.test(pathname) ||
    dashboardPattern.test(pathname) ||
    authPattern.test(pathname)
  ) {
    return <Outlet />
  }

  // All other public routes → redirect to maintenance page
  return <AppNavigate to="/maintenance" replace />
}
