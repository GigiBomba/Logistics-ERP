import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuth } from "@/contexts/auth-provider"

interface ProtectedRouteProps {
  /** Required roles — if set, user must have one of these roles */
  roles?: string[]
  /** Optional fallback redirect path (default: /login) */
  redirectTo?: string
  /** Optional children (if omitted, renders an Outlet for nested routes) */
  children?: React.ReactNode
}

/**
 * Route guard that enforces authentication and optional role-based access.
 *
 * - Unauthenticated users are redirected to `/login` (or `redirectTo`).
 * - A `from` location is passed in state so the login page can redirect back.
 * - If `roles` is provided, users without a matching role see a 404-like page
 *   (or you can customise by checking the component's fallback).
 */
export function ProtectedRoute({
  roles,
  redirectTo = "/login",
  children,
}: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth()
  const location = useLocation()

  // ── Not authenticated → redirect ──────────────────────────────────
  if (!isAuthenticated) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />
  }

  // ── Role check ────────────────────────────────────────────────────
  if (roles && roles.length > 0) {
    const userRole = user?.role ?? ""
    if (!roles.includes(userRole)) {
      // Redirect to home for unauthorized roles
      return <Navigate to="/" replace />
    }
  }

  // ── Authorized ────────────────────────────────────────────────────
  return children ? <>{children}</> : <Outlet />
}
