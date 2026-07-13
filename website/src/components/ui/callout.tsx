import * as React from "react"
import { cn } from "@/lib/utils"
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react"

const calloutVariants = {
  info: {
    container: "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300",
    icon: Info,
    iconColor: "text-blue-500 dark:text-blue-400",
  },
  warning: {
    container: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300",
    icon: AlertTriangle,
    iconColor: "text-amber-500 dark:text-amber-400",
  },
  success: {
    container: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
    icon: CheckCircle2,
    iconColor: "text-emerald-500 dark:text-emerald-400",
  },
  danger: {
    container: "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300",
    icon: XCircle,
    iconColor: "text-red-500 dark:text-red-400",
  },
} as const

export type CalloutVariant = keyof typeof calloutVariants

export interface CalloutProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: CalloutVariant
  icon?: React.ReactNode
  title?: string
}

export function Callout({
  className,
  variant = "info",
  icon,
  title,
  children,
  ...props
}: CalloutProps) {
  const { container, icon: DefaultIcon, iconColor } = calloutVariants[variant]

  const IconElement = icon ?? <DefaultIcon className={cn("h-5 w-5 shrink-0 mt-0.5", iconColor)} aria-hidden="true" />

  return (
    <div
      className={cn(
        "relative flex gap-3 rounded-lg border p-4",
        container,
        className
      )}
      {...props}
    >
      {typeof IconElement === "object" && React.isValidElement(IconElement) ? (
        IconElement
      ) : (
        <span className={cn("h-5 w-5 shrink-0", iconColor)}>{IconElement}</span>
      )}
      <div className="flex-1 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        <div className="text-sm [&_p]:leading-relaxed">{children}</div>
      </div>
    </div>
  )
}
