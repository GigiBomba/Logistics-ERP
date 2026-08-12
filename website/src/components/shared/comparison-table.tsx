import type { LucideIcon } from "lucide-react"
import { Check, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { useLocale } from "@/i18n/locale-context"

interface ComparisonColumn {
  label: string
  icon?: LucideIcon
}

interface ComparisonRow {
  feature: string
  values: (string | boolean)[]
}

interface ComparisonTableProps {
  columns: ComparisonColumn[]
  rows: ComparisonRow[]
  className?: string
}

export function ComparisonTable({ columns, rows, className }: ComparisonTableProps) {
  const { t } = useLocale()
  if (columns.length === 0 || rows.length === 0) {
    return <div className="text-center py-8 text-muted-foreground text-sm">{t("common.noDataAvailable")}</div>
  }

  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 min-w-[160px] bg-background px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {t("common.feature")}
            </th>
            {columns.map((col, i) => (
              <th
                key={i}
                className="bg-muted/50 px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                <div className="flex items-center justify-center gap-1.5">
                  {col.icon && <col.icon className="h-4 w-4" />}
                  {col.label}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={cn(
                "border-t border-border transition-colors hover:bg-muted/30",
                rowIndex % 2 === 1 && "bg-muted/10"
              )}
            >
              <td className="sticky left-0 z-10 min-w-[160px] bg-background px-4 py-3 font-medium">
                {row.feature}
              </td>
              {row.values.map((value, colIndex) => (
                <td
                  key={colIndex}
                  className="px-4 py-3 text-center"
                >
                  {typeof value === "boolean" ? (
                    value ? (
                      <Check className="mx-auto h-5 w-5 text-green-600" />
                    ) : (
                      <X className="mx-auto h-5 w-5 text-red-500" />
                    )
                  ) : (
                    <span className="text-muted-foreground">{value}</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
