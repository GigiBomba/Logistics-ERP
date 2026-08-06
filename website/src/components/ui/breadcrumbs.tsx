import * as React from "react"
import { cn } from "@/lib/utils"
import { ChevronRight } from "lucide-react"
import { useLocale } from "@/i18n/locale-context"
import { JsonLd, breadcrumbSchema } from "@/components/seo/structured-data"

export interface BreadcrumbItem {
  label: React.ReactNode
  href?: string
}

export interface BreadcrumbsProps extends React.HTMLAttributes<HTMLElement> {
  items: BreadcrumbItem[]
  separator?: React.ReactNode
}

export function Breadcrumbs({
  items,
  separator = <ChevronRight className="h-4 w-4" />,
  className,
  ...props
}: BreadcrumbsProps) {
  const { t } = useLocale()

  // Build breadcrumb structured data items from props, resolving string labels
  const breadcrumbItems = items.map((item) => ({
    name: typeof item.label === "string" ? item.label : "",
    url: item.href
      ? item.href.startsWith("http")
        ? item.href
        : `https://operionerp.xyz${item.href.startsWith("/") ? "" : "/"}${item.href}`
      : "",
  }))

  return (
    <>
      {breadcrumbItems.length > 0 && (
        <JsonLd data={breadcrumbSchema(breadcrumbItems)} />
      )}
      <nav aria-label={t("common.breadcrumb")} className={cn("", className)} {...props}>
        <ol className="flex items-center gap-1.5 text-sm text-muted-foreground">
          {items.map((item, index) => {
            const isLast = index === items.length - 1

            return (
              <li key={index} className="flex items-center gap-1.5">
                {index > 0 && (
                  <span className="text-muted-foreground/50" aria-hidden="true">
                    {separator}
                  </span>
                )}
                {isLast || !item.href ? (
                  <span
                    className={cn(
                      isLast ? "font-medium text-foreground" : ""
                    )}
                    aria-current={isLast ? "page" : undefined}
                  >
                    {item.label}
                  </span>
                ) : (
                  <a
                    href={item.href}
                    className="transition-colors hover:text-foreground"
                  >
                    {item.label}
                  </a>
                )}
              </li>
            )
          })}
        </ol>
      </nav>
    </>
  )
}
