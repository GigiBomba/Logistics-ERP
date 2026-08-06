import { cn } from "@/lib/utils"

type StatusType =
  | "operational"
  | "degraded"
  | "outage"
  | "maintenance"
  | "unknown"
  | "active"
  | "inactive"
  | "pending"
  | "success"
  | "warning"
  | "error"

interface StatusBadgeProps {
  status: StatusType
  label?: string
  className?: string
  showDot?: boolean
}

const statusConfig: Record<StatusType, { dot: string; bg: string; text: string; defaultLabel: string }> = {
  operational: {
    dot: "bg-green-500",
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-300",
    defaultLabel: "Operational",
  },
  degraded: {
    dot: "bg-yellow-500",
    bg: "bg-yellow-100 dark:bg-yellow-900/30",
    text: "text-yellow-700 dark:text-yellow-300",
    defaultLabel: "Degraded",
  },
  outage: {
    dot: "bg-red-500",
    bg: "bg-red-100 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-300",
    defaultLabel: "Outage",
  },
  maintenance: {
    dot: "bg-blue-500",
    bg: "bg-blue-100 dark:bg-blue-900/30",
    text: "text-blue-700 dark:text-blue-300",
    defaultLabel: "Maintenance",
  },
  unknown: {
    dot: "bg-gray-400",
    bg: "bg-gray-100 dark:bg-gray-800/60",
    text: "text-gray-600 dark:text-gray-300",
    defaultLabel: "Unknown",
  },
  active: {
    dot: "bg-green-500",
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-300",
    defaultLabel: "Active",
  },
  inactive: {
    dot: "bg-gray-400",
    bg: "bg-gray-100 dark:bg-gray-800",
    text: "text-gray-600 dark:text-gray-400",
    defaultLabel: "Inactive",
  },
  pending: {
    dot: "bg-yellow-500",
    bg: "bg-yellow-100 dark:bg-yellow-900/30",
    text: "text-yellow-700 dark:text-yellow-300",
    defaultLabel: "Pending",
  },
  success: {
    dot: "bg-green-500",
    bg: "bg-green-100 dark:bg-green-900/30",
    text: "text-green-700 dark:text-green-300",
    defaultLabel: "Success",
  },
  warning: {
    dot: "bg-yellow-500",
    bg: "bg-yellow-100 dark:bg-yellow-900/30",
    text: "text-yellow-700 dark:text-yellow-300",
    defaultLabel: "Warning",
  },
  error: {
    dot: "bg-red-500",
    bg: "bg-red-100 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-300",
    defaultLabel: "Error",
  },
}

export function StatusBadge({
  status,
  label,
  className,
  showDot = true,
}: StatusBadgeProps) {
  const config = statusConfig[status]

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        config.bg,
        config.text,
        className
      )}
    >
      {showDot && (
        <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} aria-hidden="true" />
      )}
      {label ?? config.defaultLabel}
    </span>
  )
}
