import { Outlet, useLocation } from "react-router"
import { AppNavigate } from "@/components/navigation/app-navigate"
import { useAuth } from "@/contexts/auth-provider"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import { RequireRole } from "./require-role"
import type { UserRole } from "@/types"

interface ProtectedRouteProps {
  requireAdmin?: boolean
  allowedRoles?: UserRole[]
}

export function ProtectedRoute({ requireAdmin = false, allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, isAdmin, user } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!isAuthenticated) {
    const returnUrl = location.pathname + location.search
    return <AppNavigate to={`/login?returnUrl=${encodeURIComponent(returnUrl)}`} replace />
  }

  if (allowedRoles) {
    if (!user || !allowedRoles.includes(user.role)) {
      return <AppNavigate to="/dashboard" replace />
    }
    return <Outlet />
  }

  if (requireAdmin && !isAdmin) {
    return <AppNavigate to="/dashboard" replace />
  }

  return <Outlet />
}

export function AdminRoute() {
  return <ProtectedRoute requireAdmin />
}

export { RequireRole }
