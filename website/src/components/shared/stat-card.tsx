import type { LucideIcon } from "lucide-react"
import { TrendingUp, TrendingDown } from "lucide-react"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"

interface StatCardProps {
  value: string
  label: string
  icon?: LucideIcon
  trend?: {
    direction: "up" | "down"
    value: string
  }
  className?: string
}

export function StatCard({ value, label, icon: Icon, trend, className }: StatCardProps) {
  const { t } = useLocale()
  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-6 text-card-foreground shadow-sm transition-shadow hover:shadow-md",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-3xl font-bold tracking-tight">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
        {Icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-primary">
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
      {trend && (
        <div className="mt-4 flex items-center gap-1 text-sm">
          {trend.direction === "up" ? (
            <TrendingUp className="h-4 w-4 text-green-600" />
          ) : (
            <TrendingDown className="h-4 w-4 text-red-600" />
          )}
          <span
            className={cn(
              "font-medium",
              trend.direction === "up" ? "text-green-600" : "text-red-600"
            )}
          >
            {trend.value}
          </span>
          <span className="text-muted-foreground">{t("common.vsLastMonth")}</span>
        </div>
      )}
    </div>
  )
}
