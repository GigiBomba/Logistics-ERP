import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg"
  className?: string
}

export function LoadingSpinner({ size = "md", className }: LoadingSpinnerProps) {
  const { t } = useLocale()
  const sizeMap = { sm: "h-4 w-4", md: "h-8 w-8", lg: "h-12 w-12" }
  return (
    <div role="status" className={cn(className)}>
      <Loader2 className={cn("animate-spin text-muted-foreground", sizeMap[size])} />
      <span className="sr-only">{t("common.loading")}</span>
    </div>
  )
}

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />
}

export function PageSkeleton() {
  return (
    <div className="container-wide py-12 space-y-8">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-6 w-96" />
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-48" />
        ))}
      </div>
    </div>
  )
}
