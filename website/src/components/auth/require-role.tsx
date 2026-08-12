import { AppNavigate } from "@/components/navigation/app-navigate"
import { useAuth } from "@/contexts/auth-provider"
import { LoadingSpinner } from "@/components/ui/loading-spinner"
import type { UserRole } from "@/types"

interface RequireRoleProps {
  roles: UserRole[]
  children: React.ReactNode
  /** Optional: show fallback UI instead of redirecting to /dashboard */
  fallback?: React.ReactNode
}

export function RequireRole({ roles, children, fallback }: RequireRoleProps) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!user) return <AppNavigate to="/login" replace />

  if (!roles.includes(user.role)) {
    if (fallback) return <>{fallback}</>
    return <AppNavigate to="/dashboard" replace />
  }

  return <>{children}</>
}
